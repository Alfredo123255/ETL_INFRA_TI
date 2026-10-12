"""Ficha de servidor según schema.sql; no calcula el total de GHz del backend."""
import re
from decimal import Decimal
from etl.errores import DatosIncompletos
from etl.oid_util import SYSTEM, filas as filas_oid
from etl.oids.servidor import OIDS_IDENTIDAD, TABLAS_HPE, OIDS_ENTIDAD_NIC, MODELOS_CONTROLADORA_HPE
from etl.normalizacion.reglas import mb_a_gb, kb_a_gb, mhz_a_ghz, dividir, calcular_hilos
from etl.normalizacion.inferencias import familia_cpu, generacion_ram, corriente_fuente_hpe, potencia_nominal_modelo
from etl.normalizacion.estados import (
    normalizar_estado, CONDICION_HPE, ESTADO_CPU_HPE, ESTADO_RAM_HPE, ESTADO_NIC_HPE,
)

MARCAS_CPU = {2: "Intel", 3: "AMD", 4: "Cyrix", 5: "TI", 6: "NexGen", 7: "Compaq",
              8: "Samsung", 9: "Mitsubishi", 10: "MIPS"}
TIPOS_DISCO = {2: "SCSI", 3: "SATA", 4: "SAS", 5: "NVMe"}
RPM_DISCO = {2: 7200, 3: 10000, 4: 15000, 5: 0}
NIVELES_RAID = {2: "RAID0", 3: "RAID1", 4: "RAID4", 5: "RAID5", 7: "RAID6",
                8: "RAID50", 9: "RAID60", 10: "RAID1 ADM", 11: "RAID10 ADM", 12: "RAID10"}


def marca_disco(modelo):
    """Reconoce la marca solo si aparece explícita al inicio del modelo SNMP."""
    coincidencia = re.match(r"^(HPE|HP)\b", modelo, re.I) if modelo else None
    return coincidencia.group(1).upper() if coincidencia else None


def texto(valor):
    if valor is None:
        return None
    if isinstance(valor, bytes):
        value = valor.decode("utf-8", errors="replace")
    else:
        value = valor.prettyPrint() if hasattr(valor, "prettyPrint") else str(valor)
    return value.strip() or None


def nombre_y_version_so(nombre, version):
    """Conserva ambos datos en la única columna version_so disponible."""
    nombre, version = texto(nombre), texto(version)
    if not nombre or not version:
        return nombre or version
    if version.casefold().startswith(nombre.casefold()):
        return version
    return f"{nombre} {version}"


def numero(valor):
    if valor is None:
        return None
    return int(valor)


def filas(datos, columnas):
    """Agrupa por el índice SNMP completo, incluyendo índices compuestos."""
    resultado = {}
    for campo, columna in columnas.items():
        prefijo = columna + "."
        for oid, valor in datos.items():
            if oid.startswith(prefijo):
                indice = tuple(map(int, oid[len(prefijo):].split(".")))
                resultado.setdefault(indice, {})[campo] = valor
    return [(indice, resultado[indice]) for indice in sorted(resultado)]


def mac(valor):
    if valor is None:
        return None
    octetos = valor.asOctets() if hasattr(valor, "asOctets") else valor
    if not isinstance(octetos, bytes) or len(octetos) != 6:
        return None
    return ":".join(f"{octeto:02x}" for octeto in octetos)


def normalizar_servidor_hpe(datos_crudos, *, fecha_actualizacion, tipo="RACKEABLE"):
    if tipo not in ("AUTO", "RACKEABLE", "BLADE"):
        raise DatosIncompletos("Tipo de servidor inválido.")
    identidad = {campo: datos_crudos.get(oid) for campo, oid in OIDS_IDENTIDAD.items()}
    serie = texto(identidad["numero_serie"])
    hostname = texto(identidad["hostname"]) or texto(identidad["sys_name"])
    modelo = texto(identidad["modelo"])
    if not serie or not hostname or not modelo:
        raise DatosIncompletos("El equipo no proporciona serie, hostname o modelo para registrarlo.")
    blade = bool(re.search(r"\bBL\d", modelo, re.IGNORECASE))
    if tipo == "AUTO":
        tipo = "BLADE" if blade else "RACKEABLE"
    if blade and tipo != "BLADE":
        raise DatosIncompletos("El modelo detectado es blade; debe indicarse tipo BLADE.")
    tablas = {nombre: filas(datos_crudos, columnas) for nombre, columnas in TABLAS_HPE.items()}
    entidades_nic = {}
    for _, entidad in filas(datos_crudos, OIDS_ENTIDAD_NIC):
        if numero(entidad.get("clase")) != 9:  # entPhysicalClass: module(9)
            continue
        parte = texto(entidad.get("numero_parte"))
        serie_entidad = texto(entidad.get("numero_serial"))
        if parte and serie_entidad:
            entidades_nic.setdefault(parte.upper(), []).append(serie_entidad)
    sensores = [numero(f.get("celsius")) for _, f in tablas["temperatura"]
                if numero(f.get("ubicacion")) == 11 and numero(f.get("celsius")) is not None
                and numero(f.get("celsius")) >= 0]
    consumo = numero(identidad["consumo_electrico_w"])
    generacion = re.search(r"\bGen\d+\b", modelo, re.IGNORECASE)
    activo = {
        "numero_serie": serie, "hostname": hostname, "fabricante": "HPE", "modelo": modelo,
        "generacion": generacion.group() if generacion else None, "tipo_activo": "SERVIDOR",
        "estado_operativo": normalizar_estado(identidad["estado_operativo"], CONDICION_HPE),
        "version_firmware": texto(identidad["version_firmware"]),
        "ultima_actualizacion": fecha_actualizacion,
        "temperatura": max(sensores) if sensores else None,
        "consumo_electrico_w": consumo if consumo is not None and consumo >= 0 else None,
    }
    direcciones = [texto(f.get("direccion")) for _, f in tablas["ip"]]
    direcciones = [ip for ip in direcciones if ip and not ip.startswith("127.") and ip != "0.0.0.0"]
    if len(direcciones) > 1:
        raise DatosIncompletos("El equipo proporciona varias IP de sistema operativo; falta una regla de selección.")
    servidor = {"tipo": tipo, "version_so": nombre_y_version_so(
                    identidad["nombre_so"], identidad["version_so"]),
                "ip_sistema_operativo": direcciones[0] if direcciones else None}
    componentes = {nombre: [] for nombre in (
        "cpu", "ram", "disco", "controladora_raid", "tarjeta_red", "ventilador", "fuente_poder")}
    mediciones = []
    for indice, f in tablas["cpu"]:
        cpu = {"numero_serial": texto(f.get("numero_serial")), "marca": MARCAS_CPU.get(numero(f.get("marca"))),
               "modelo": texto(f.get("modelo")), "familia": familia_cpu(texto(f.get("modelo"))),
               "velocidad_ghz": mhz_a_ghz(numero(f.get("velocidad_mhz"))),
               "cantidad_nucleos": numero(f.get("cantidad_nucleos")),
               "cantidad_hilos": calcular_hilos(numero(f.get("cantidad_nucleos")), numero(f.get("hilos_por_nucleo"))),
               "estado": normalizar_estado(f.get("estado"), ESTADO_CPU_HPE)}
        for nivel in (1, 2, 3):
            capacidades = [numero(c.get("capacidad_kb")) for i, c in tablas["cache"]
                           if i[0] == indice[0] and numero(c.get("nivel")) == nivel
                           and numero(c.get("capacidad_kb")) is not None and numero(c.get("capacidad_kb")) >= 0]
            cpu[f"cache_l{nivel}_mb"] = dividir(sum(capacidades), 1024) if capacidades else None
        componentes["cpu"].append(cpu)
    for _, f in tablas["ram"]:
        componentes["ram"].append({"numero_serial": texto(f.get("numero_serial")),
            "marca": texto(f.get("marca")), "modelo": texto(f.get("modelo")),
            "generacion": generacion_ram(texto(f.get("modelo"))),
            "velocidad_mhz": numero(f.get("velocidad_mhz")),
            "capacidad_gb": kb_a_gb(numero(f.get("capacidad_kb"))),
            "estado": normalizar_estado(f.get("estado"), ESTADO_RAM_HPE)})
    for _, f in tablas["disco"]:
        componentes["disco"].append({"numero_serial": texto(f.get("numero_serial")),
            "marca": marca_disco(texto(f.get("modelo"))), "modelo": texto(f.get("modelo")), "tipo": TIPOS_DISCO.get(numero(f.get("tipo"))),
            "capacidad_gb": mb_a_gb(numero(f.get("capacidad_mb"))),
            "velocidad_rpm": RPM_DISCO.get(numero(f.get("rotacion"))),
            "estado": normalizar_estado(f.get("estado"), CONDICION_HPE)})
    for indice, f in tablas["controladora_raid"]:
        unidades = [u for i, u in tablas["unidad_logica"] if i[0] == indice[0]]
        componentes["controladora_raid"].append({"numero_serial": texto(f.get("numero_serial")),
            "modelo": MODELOS_CONTROLADORA_HPE.get(numero(f.get("modelo"))),
            "raid": NIVELES_RAID.get(numero(unidades[0].get("raid"))) if unidades else None,
            "estado": normalizar_estado(f.get("estado"), CONDICION_HPE)})
    if tipo == "RACKEABLE":
        for nombre, campos in (("ventilador", ("velocidad_rpm",)), ("fuente_poder", ())):
            for _, f in tablas[nombre]:
                componente = {"numero_serial": texto(f.get("numero_serial")), "modelo": texto(f.get("modelo")),
                              "estado": normalizar_estado(f.get("estado"), CONDICION_HPE)}
                componente.update({campo: numero(f.get(campo)) for campo in campos})
                if nombre == "fuente_poder":
                    capacidad = numero(f.get("capacidad_max_w"))
                    componente["consumo_w"] = (capacidad if capacidad is not None and capacidad > 0
                        else potencia_nominal_modelo(componente["modelo"]))
                    componente["tipo_corriente"] = corriente_fuente_hpe(
                        texto(f.get("modelo")), texto(f.get("numero_parte")))
                componentes[nombre].append(componente)
        tarjetas = {}
        partes_por_grupo = {}
        for indice, f in tablas["tarjeta_red"]:
            slot = numero(f.get("slot"))
            # Sin slot conocido se evita agrupar dos tarjetas independientes.
            grupo = ("slot", slot) if slot is not None and slot >= 0 else ("indice", indice)
            parte = texto(f.get("numero_parte"))
            if parte:
                partes_por_grupo[grupo] = parte.upper()
            modelo_tarjeta = texto(f.get("modelo"))
            tarjeta = tarjetas.setdefault(grupo, {"numero_serial": None,
                "marca": "HPE" if modelo_tarjeta and re.match(r"^HPE\b", modelo_tarjeta, re.I) else None,
                "modelo": modelo_tarjeta, "puertos": []})
            velocidad = numero(f.get("velocidad_mbps"))
            if velocidad is None or velocidad <= 0:
                bps = numero(f.get("velocidad_bps"))
                velocidad = Decimal(bps) / 1000000 if bps is not None and bps > 0 else None
            estado = normalizar_estado(f.get("estado"), ESTADO_NIC_HPE) if f.get("estado") is not None else normalizar_estado(f.get("condicion"), CONDICION_HPE)
            tarjeta["puertos"].append({"numero_puerto": texto(f.get("numero_puerto")),
                "mac_address": mac(f.get("mac_address")),
                "velocidad": f"{velocidad} Mbps" if velocidad is not None else None, "estado": estado})
        prioridad = {"Encendido": 0, "Degradado": 1, "Apagado": 2}
        for grupo, tarjeta in tarjetas.items():
            parte = partes_por_grupo.get(grupo)
            # No atribuir un serial si la misma parte identifica varias NIC.
            coincidencias = entidades_nic.get(parte, []) if parte else []
            if len(coincidencias) == 1 and list(partes_por_grupo.values()).count(parte) == 1:
                tarjeta["numero_serial"] = coincidencias[0]
            tarjeta["cantidad_puertos"] = len(tarjeta["puertos"])
            tarjeta["estado"] = max((p["estado"] for p in tarjeta["puertos"]), key=prioridad.get)
            componentes["tarjeta_red"].append(tarjeta)
    # Misma base que el backend: GHz de cada CPU multiplicados por sus núcleos.
    # El total sigue siendo derivado en el backend; aquí solo se guarda la métrica de uso.
    porcentajes = [numero(f.get("porcentaje")) for _, f in tablas["uso_cpu"]]
    cpus = componentes["cpu"]
    capacidad_completa = cpus and all(
        c["velocidad_ghz"] is not None and c["velocidad_ghz"] > 0
        and c["cantidad_nucleos"] is not None and c["cantidad_nucleos"] > 0
        for c in cpus)
    if porcentajes and all(p is not None and 0 <= p <= 100 for p in porcentajes) and capacidad_completa:
        capacidad_ghz = sum(c["velocidad_ghz"] * c["cantidad_nucleos"] for c in cpus)
        uso = capacidad_ghz * Decimal(sum(porcentajes)) / Decimal(len(porcentajes) * 100)
        mediciones.append({"nombre_metrica": "cpu_uso_ghz", "valor": uso})
    total, libre = numero(identidad["ram_total_mb"]), numero(identidad["ram_libre_mb"])
    if total is not None and libre is not None and 0 <= libre <= total:
        mediciones.append({"nombre_metrica": "ram_uso_gb", "valor": mb_a_gb(total - libre)})
    for campo in ("temperatura", "consumo_electrico_w"):
        if activo[campo] is not None:
            mediciones.append({"nombre_metrica": campo, "valor": activo[campo]})
    return {"activo": activo, "servidor": servidor, "componentes": componentes,
            "mediciones": mediciones, "ubicacion_snmp": texto(identidad["ubicacion_snmp"])}


def normalizar_servidor(datos_crudos, *, fabricante="HPE", fecha_actualizacion, tipo="RACKEABLE"):
    from etl.errores import PerfilNoSoportado
    normalizadores = {"HPE": normalizar_servidor_hpe, "Huawei": normalizar_servidor_huawei}
    normalizador = normalizadores.get(fabricante)
    if normalizador is None:
        raise PerfilNoSoportado("Fabricante sin normalizador de servidor implementado.")
    return normalizador(datos_crudos, fecha_actualizacion=fecha_actualizacion, tipo=tipo)


IBMC = "1.3.6.1.4.1.2011.2.235.1.1"
IF = "1.3.6.1.2.1.2.2.1"
IFX = "1.3.6.1.2.1.31.1.1.1"

def _s(datos, oid):
    return texto(datos.get(oid))


def _n(datos, oid):
    return numero(datos.get(oid))


def _estado(health, *, cero_bien=False, power=None):
    if power in (0, 1, "poweroff", "off"):
        return "Apagado"
    if health == (0 if cero_bien else 1):
        return "Encendido"
    return "Degradado"


def _cantidad(valor, unidad):
    valor = texto(valor)
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*" + unidad, valor or "", re.I)
    return Decimal(match.group(1)) if match else None


def _mediciones(activo, adicionales=()):
    valores = [(nombre, activo[nombre]) for nombre in ("temperatura", "consumo_electrico_w")]
    valores.extend(adicionales)
    return [{"nombre_metrica": nombre, "valor": valor} for nombre, valor in valores if valor is not None]


def _base(serie, hostname, modelo, tipo, estado, fecha, *, generacion=None, firmware=None,
          temperatura=None, consumo=None):
    if not serie or not hostname or not modelo:
        raise DatosIncompletos("Huawei no proporciona serie, hostname o modelo inequívoco.")
    return {"numero_serie": serie, "hostname": hostname, "fabricante": "Huawei",
            "modelo": modelo, "generacion": generacion, "tipo_activo": tipo,
            "estado_operativo": estado, "version_firmware": firmware,
            "ultima_actualizacion": fecha, "temperatura": temperatura,
            "consumo_electrico_w": consumo}


def _puertos(datos):
    resultado = []
    for indice, fila in filas_oid(datos, {"nombre": IFX + ".1", "velocidad": IFX + ".15",
                                      "operativo": IF + ".8", "mac": IF + ".6"}):
        bruto = fila.get("mac")
        octetos = bruto.asOctets() if hasattr(bruto, "asOctets") else bruto
        mac = ":".join(f"{x:02x}" for x in octetos) if isinstance(octetos, bytes) and len(octetos) == 6 else None
        mbps = numero(fila.get("velocidad"))
        resultado.append({"numero_puerto": texto(fila.get("nombre")) or indice,
                          "mac_address": mac,
                          "velocidad": f"{mbps} Mbps" if mbps else None,
                          "estado": "Encendido" if numero(fila.get("operativo")) == 1 else "Apagado"})
    return resultado


def normalizar_servidor_huawei(datos, *, fecha_actualizacion, tipo="AUTO"):
    if tipo not in ("AUTO", "RACKEABLE", "BLADE"):
        raise DatosIncompletos("Tipo de servidor inválido.")
    d = IBMC
    slot = _s(datos, d + ".1.15.0")
    serie_chasis = _s(datos, d + ".44.7.0")
    if bool(slot) != bool(serie_chasis):
        raise DatosIncompletos("La identidad blade iBMC es incompleta: faltan ranura o serie de chasis.")
    blade = bool(slot and serie_chasis)
    if tipo != "AUTO" and (tipo == "BLADE") != blade:
        raise DatosIncompletos("El tipo blade/rack no coincide con la evidencia iBMC.")
    modelo = _s(datos, d + ".1.6.0")
    generacion = re.search(r"\bV\d+\b", modelo or "", re.I)
    power = _n(datos, d + ".1.12.0")
    # iBMC temperatureReading se expresa en décimas de °C; 65535 indica
    # lectura no disponible (por ejemplo, CPU con el servidor apagado).
    temperaturas = [dividir(valor, 10) for _, sensor in filas_oid(datos, {
        "lectura": d + ".26.50.1.3"})
        if (valor := numero(sensor.get("lectura"))) is not None and 0 <= valor < 65535]
    activo = _base(_s(datos, d + ".1.7.0"), _s(datos, d + ".1.9.0") or _s(datos, SYSTEM["hostname"]),
                   modelo, "SERVIDOR", _estado(_n(datos, d + ".1.1.0"), power=0 if power == 1 else None),
                   fecha_actualizacion, generacion=generacion.group() if generacion else None,
                   temperatura=max(temperaturas) if temperaturas else None,
                   consumo=_n(datos, d + ".1.13.0"))
    componentes = {nombre: [] for nombre in ("cpu", "ram", "disco", "controladora_raid",
                                               "tarjeta_red", "ventilador", "fuente_poder")}
    for _, f in filas_oid(datos, {"marca": d + ".15.50.1.2", "familia": d + ".15.50.1.3",
                              "modelo": d + ".15.50.1.4", "mhz": d + ".15.50.1.5",
                              "estado": d + ".15.50.1.6", "nucleos": d + ".15.50.1.12",
                              "hilos": d + ".15.50.1.13"}):
        mhz = _cantidad(f.get("mhz"), "MHz")
        componentes["cpu"].append({"numero_serial": None, "marca": texto(f.get("marca")),
            "familia": texto(f.get("familia")), "modelo": texto(f.get("modelo")),
            "velocidad_ghz": dividir(mhz, 1000), "cantidad_nucleos": numero(f.get("nucleos")),
            "cantidad_hilos": numero(f.get("hilos")),
            "estado": _estado(numero(f.get("estado")))})
    for _, f in filas_oid(datos, {"marca": d + ".16.50.1.3", "gb": d + ".16.50.1.4",
                              "mhz": d + ".16.50.1.5", "estado": d + ".16.50.1.6",
                              "modelo": d + ".16.50.1.10", "tipo": d + ".16.50.1.11",
                              "serie": d + ".16.50.1.12"}):
        componentes["ram"].append({"numero_serial": texto(f.get("serie")),
            "marca": texto(f.get("marca")), "modelo": texto(f.get("modelo")),
            "generacion": texto(f.get("tipo")), "capacidad_gb": _cantidad(f.get("gb"), "GB"),
            "velocidad_mhz": _cantidad(f.get("mhz"), "MHz"),
            "estado": _estado(numero(f.get("estado")))})
    for _, f in filas_oid(datos, {"estado": d + ".18.50.1.3", "serie": d + ".18.50.1.7",
                              "modelo": d + ".18.50.1.8", "marca": d + ".18.50.1.9",
                              "gb": d + ".18.50.1.12"}):
        modelo_disco = texto(f.get("modelo"))
        componentes["disco"].append({"numero_serial": texto(f.get("serie")),
            "marca": texto(f.get("marca")), "modelo": modelo_disco,
            "tipo": "NVMe" if modelo_disco and "NVME" in modelo_disco.upper() else
                    "SAS" if modelo_disco and "SAS" in modelo_disco.upper() else None,
            "capacidad_gb": numero(f.get("gb")), "velocidad_rpm": None,
            "estado": _estado(numero(f.get("estado")))})
    niveles_por_controladora = {}
    for indice, f in filas_oid(datos, {"nivel": d + ".37.50.1.3"}):
        nivel = texto(f.get("nivel"))
        if nivel:
            niveles_por_controladora.setdefault(indice[0], []).append(nivel)
    for indice, f in filas_oid(datos, {"nombre": d + ".36.50.1.2",
                                      "modelo": d + ".36.50.1.3",
                                      "estado": d + ".36.50.1.7"}):
        niveles = list(dict.fromkeys(niveles_por_controladora.get(indice[0], [])))
        componentes["controladora_raid"].append({
            "numero_serial": None,
            "modelo": texto(f.get("modelo")) or texto(f.get("nombre")),
            "raid": ", ".join(niveles) if niveles else None,
            "estado": _estado(numero(f.get("estado")), cero_bien=True),
        })
    if not blade:
        for _, f in filas_oid(datos, {"modelo": d + ".6.50.1.4", "estado": d + ".6.50.1.7",
                                  "serie": d + ".6.50.1.15", "corriente": d + ".6.50.1.3",
                                  "capacidad_max_w": d + ".6.50.1.6"}):
            modelo_fuente = texto(f.get("modelo"))
            capacidad = numero(f.get("capacidad_max_w"))
            componentes["fuente_poder"].append({"numero_serial": texto(f.get("serie")),
                "modelo": modelo_fuente,
                "consumo_w": capacidad if capacidad is not None and capacidad > 0
                    else potencia_nominal_modelo(modelo_fuente),
                "tipo_corriente": {1: "AC", 2: "DC"}.get(numero(f.get("corriente"))),
                "estado": _estado(numero(f.get("estado")))})
        for _, f in filas_oid(datos, {"rpm": d + ".8.50.1.2", "estado": d + ".8.50.1.4",
                                  "modelo": d + ".8.50.1.7"}):
            componentes["ventilador"].append({"numero_serial": None,
                "modelo": texto(f.get("modelo")), "velocidad_rpm": numero(f.get("rpm")),
                "estado": _estado(numero(f.get("estado")))})
    tarjetas = filas_oid(datos, {"modelo": d + ".25.50.1.5", "nombre": d + ".25.50.1.7",
                                "marca": d + ".25.50.1.9",
                            "estado": d + ".25.50.1.18"})
    puertos = _puertos(datos)
    for posicion, (_, f) in enumerate(tarjetas):
        puerto = puertos[posicion:posicion + 1]
        componentes["tarjeta_red"].append({"numero_serial": texto(f.get("nombre")),
            "marca": texto(f.get("marca")), "modelo": texto(f.get("modelo")),
            "estado": _estado(numero(f.get("estado"))), "cantidad_puertos": len(puerto),
            "puertos": puerto})
    cpu_pct = _n(datos, d + ".1.23.0")
    ram_pct = _n(datos, d + ".1.25.0")
    capacidad_cpu = sum((c["velocidad_ghz"] or 0) * (c["cantidad_nucleos"] or 0)
                        for c in componentes["cpu"])
    total_ram = sum(c["capacidad_gb"] or 0 for c in componentes["ram"])
    extras = [("cpu_uso_ghz", capacidad_cpu * Decimal(cpu_pct) / 100 if
               capacidad_cpu and cpu_pct is not None and 0 <= cpu_pct <= 100 else None),
              ("ram_uso_gb", total_ram * Decimal(ram_pct) / 100 if
               total_ram and ram_pct is not None and 0 <= ram_pct <= 100 else None)]
    return {"activo": activo, "servidor": {"tipo": "BLADE" if blade else "RACKEABLE",
            "version_so": None, "ip_sistema_operativo": None},
            "componentes": componentes, "mediciones": _mediciones(activo, extras),
            "ubicacion_snmp": _s(datos, SYSTEM["ubicacion"])}
