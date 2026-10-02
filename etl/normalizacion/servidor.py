"""Ficha de servidor según schema.sql; no calcula el total de GHz del backend."""
import re
from decimal import Decimal
from etl.errores import DatosIncompletos
from etl.oids.servidor import OIDS_IDENTIDAD, TABLAS_HPE, MODELOS_CONTROLADORA_HPE
from etl.normalizacion.reglas import mb_a_gb, kb_a_gb, mhz_a_ghz, dividir, calcular_hilos
from etl.normalizacion.estados import (
    normalizar_estado, CONDICION_HPE, ESTADO_CPU_HPE, ESTADO_RAM_HPE, ESTADO_NIC_HPE,
)

MARCAS_CPU = {2: "Intel", 3: "AMD", 4: "Cyrix", 5: "TI", 6: "NexGen", 7: "Compaq",
              8: "Samsung", 9: "Mitsubishi", 10: "MIPS"}
TIPOS_DISCO = {2: "SCSI", 3: "SATA", 4: "SAS", 5: "NVMe"}
RPM_DISCO = {2: 7200, 3: 10000, 4: 15000, 5: 0}
NIVELES_RAID = {2: "RAID0", 3: "RAID1", 4: "RAID4", 5: "RAID5", 7: "RAID6",
                8: "RAID50", 9: "RAID60", 10: "RAID1 ADM", 11: "RAID10 ADM", 12: "RAID10"}


def texto(valor):
    if valor is None:
        return None
    if isinstance(valor, bytes):
        value = valor.decode("utf-8", errors="replace")
    else:
        value = valor.prettyPrint() if hasattr(valor, "prettyPrint") else str(valor)
    return value.strip() or None


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
    servidor = {"tipo": tipo, "version_so": texto(identidad["version_so"]),
                "ip_sistema_operativo": direcciones[0] if direcciones else None}
    componentes = {nombre: [] for nombre in (
        "cpu", "ram", "disco", "controladora_raid", "tarjeta_red", "ventilador", "fuente_poder")}
    mediciones = []
    for indice, f in tablas["cpu"]:
        cpu = {"numero_serial": texto(f.get("numero_serial")), "marca": MARCAS_CPU.get(numero(f.get("marca"))),
               "modelo": texto(f.get("modelo")), "familia": None,
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
            "marca": texto(f.get("marca")), "modelo": texto(f.get("modelo")), "generacion": None,
            "velocidad_mhz": numero(f.get("velocidad_mhz")),
            "capacidad_gb": kb_a_gb(numero(f.get("capacidad_kb"))),
            "estado": normalizar_estado(f.get("estado"), ESTADO_RAM_HPE)})
    for _, f in tablas["disco"]:
        componentes["disco"].append({"numero_serial": texto(f.get("numero_serial")),
            "marca": None, "modelo": texto(f.get("modelo")), "tipo": TIPOS_DISCO.get(numero(f.get("tipo"))),
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
        for nombre, campos in (("ventilador", ("velocidad_rpm",)), ("fuente_poder", ("consumo_w",))):
            for _, f in tablas[nombre]:
                componente = {"numero_serial": texto(f.get("numero_serial")), "modelo": texto(f.get("modelo")),
                              "estado": normalizar_estado(f.get("estado"), CONDICION_HPE)}
                componente.update({campo: numero(f.get(campo)) for campo in campos})
                if nombre == "fuente_poder":
                    componente["tipo_corriente"] = None
                componentes[nombre].append(componente)
        tarjetas = {}
        for indice, f in tablas["tarjeta_red"]:
            slot = numero(f.get("slot"))
            # Sin slot conocido se evita agrupar dos tarjetas independientes.
            grupo = ("slot", slot) if slot is not None and slot >= 0 else ("indice", indice)
            tarjeta = tarjetas.setdefault(grupo, {"numero_serial": None, "marca": None,
                "modelo": texto(f.get("modelo")), "puertos": []})
            velocidad = numero(f.get("velocidad_mbps"))
            if velocidad is None or velocidad <= 0:
                bps = numero(f.get("velocidad_bps"))
                velocidad = Decimal(bps) / 1000000 if bps is not None and bps > 0 else None
            estado = normalizar_estado(f.get("estado"), ESTADO_NIC_HPE) if f.get("estado") is not None else normalizar_estado(f.get("condicion"), CONDICION_HPE)
            tarjeta["puertos"].append({"numero_puerto": texto(f.get("numero_puerto")),
                "mac_address": mac(f.get("mac_address")),
                "velocidad": f"{velocidad} Mbps" if velocidad is not None else None, "estado": estado})
        prioridad = {"Encendido": 0, "Degradado": 1, "Apagado": 2}
        for tarjeta in tarjetas.values():
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
    normalizadores = {"HPE": normalizar_servidor_hpe}
    normalizador = normalizadores.get(fabricante)
    if normalizador is None:
        raise PerfilNoSoportado("Fabricante sin normalizador de servidor implementado.")
    return normalizador(datos_crudos, fecha_actualizacion=fecha_actualizacion, tipo=tipo)
