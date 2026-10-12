"""Ficha de arreglo Fibre Channel y componentes HPE documentados."""
import re
from decimal import Decimal
from etl.errores import DatosIncompletos, PerfilNoSoportado
from etl.oid_util import SYSTEM, filas, texto, numero
from etl.normalizacion.servidor import normalizar_servidor_hpe, marca_disco, _s, _n, _estado, _base, _mediciones
from etl.normalizacion.reglas import mb_a_gb, dividir
from etl.normalizacion.estados import CONDICION_HPE, normalizar_estado
from etl.normalizacion.inferencias import potencia_nominal_modelo

SS="1.3.6.1.4.1.232.8.2.2.1.1"
FC="1.3.6.1.4.1.232.16.2"
NIM="1.3.6.1.4.1.37447.1.3"
RAID={2:"RAID0",3:"RAID1",4:"RAID4",5:"RAID5",7:"RAID6"}
CTRL={3:"MSA1000",6:"HSV110"}
HBA={58:"HPE FCA LPe1605",85:"HPE FCA SN1600E 2P"}

def normalizar_storage_hpe(datos, *, fecha_actualizacion):
    host=normalizar_servidor_hpe(datos,fecha_actualizacion=fecha_actualizacion)
    chasis=filas(datos,{"serie":SS+".3","modelo":SS+".26","estado":SS+".11"})
    if len(chasis)!=1:
        raise DatosIncompletos("El storage no proporciona una identidad única del arreglo.")
    row=chasis[0][1]
    serie,modelo=texto(row.get("serie")),texto(row.get("modelo"))
    if not serie or not modelo:
        raise DatosIncompletos("Falta serie o modelo del arreglo storage.")
    drives=[]
    for _,d in filas(datos,{"modelo":FC+".5.1.1.3","serie":FC+".5.1.1.43",
                           "tipo":FC+".5.1.1.51","capacidad":FC+".5.1.1.38",
                           "rpm":FC+".5.1.1.50","estado":FC+".5.1.1.31"}):
        drives.append({"numero_serial":texto(d.get("serie")),"modelo":texto(d.get("modelo")),
            "marca":marca_disco(texto(d.get("modelo"))),"tipo":{2:"SCSI",3:"SATA",4:"SAS"}.get(numero(d.get("tipo"))),
            "capacidad_gb":mb_a_gb(numero(d.get("capacidad"))),
            "velocidad_rpm":{2:7200,3:10000,4:15000}.get(numero(d.get("rpm"))),
            "estado":normalizar_estado(numero(d.get("estado")),CONDICION_HPE)})
    if not drives:
        raise DatosIncompletos("El arreglo no reporta discos físicos.")
    logical=filas(datos,{"raid":FC+".3.1.1.3","capacidad":FC+".3.1.1.9"})
    raid_value=numero(logical[0][1].get("raid")) if logical else None
    controllers=[]
    for _,d in filas(datos,{"modelo":FC+".2.1.1.3","serie":FC+".2.1.1.9","estado":FC+".2.1.1.6"}):
        model_id=numero(d.get("modelo"))
        controllers.append({"modelo":CTRL.get(model_id,f"CPQFCA modelo {model_id}" if model_id else None),
            "numero_serial":texto(d.get("serie")),"raid":RAID.get(raid_value),
            "estado":normalizar_estado(numero(d.get("estado")),CONDICION_HPE)})
    if not controllers:
        raise DatosIncompletos("El arreglo no reporta controladora FC.")
    cards=list(host["componentes"]["tarjeta_red"])
    for _,d in filas(datos,{"modelo":FC+".7.1.1.3","serie":FC+".7.1.1.10",
                           "estado":FC+".7.1.1.5","puerto":FC+".7.1.1.2","wwpn":FC+".7.1.1.12"}):
        model_id=numero(d.get("modelo"))
        cards.append({"numero_serial":texto(d.get("serie")),"marca":"HPE",
            "modelo":HBA.get(model_id,f"FCA modelo {model_id}" if model_id else None),
            "estado":normalizar_estado(numero(d.get("estado")),CONDICION_HPE),"cantidad_puertos":1,
            "puertos":[{"numero_puerto":str(numero(d.get("puerto"))) if d.get("puerto") is not None else None,
                       "mac_address":texto(d.get("wwpn")),"velocidad":None,
                       "estado":normalizar_estado(numero(d.get("estado")),CONDICION_HPE)}]})
    total_mb=sum(numero(d.get("capacidad")) or 0 for _,d in filas(datos,{"capacidad":FC+".5.1.1.38"}))
    used=None
    parts=[numero(datos.get(f"{NIM}.{col}.0")) for col in (12,13,14,15)]
    if all(x is not None for x in parts):
        used=dividir((parts[1]+parts[3])*(2**32)+parts[0]+parts[2],1024**4)
    total_tb=dividir(total_mb,1024**2)
    if used is not None and used>total_tb:
        raise DatosIncompletos("La capacidad usada supera la capacidad física del arreglo.")
    activo={**host["activo"],"numero_serie":serie,"modelo":modelo,"tipo_activo":"STORAGE",
        "estado_operativo":normalizar_estado(numero(row.get("estado")),CONDICION_HPE)}
    generacion=re.search(r"\bGen\d+\b",host["activo"].get("modelo") or "",re.I)
    activo["generacion"]=generacion.group() if generacion else None
    componentes={**host["componentes"],"disco":drives,"controladora_raid":controllers,"tarjeta_red":cards}
    # La energía y la temperatura corresponden al host administrador; el arreglo no expone esas magnitudes.
    return {"activo":activo,"storage":{"protocolo_comunicacion":"Fibre Channel",
        "capacidad_total_tb":total_tb,"capacidad_usada_tb":used,"iops":None},
        "componentes":componentes,"mediciones":host["mediciones"],
        "ubicacion_snmp":texto(datos.get(SYSTEM["ubicacion"]))}


DORADO = "1.3.6.1.4.1.34774.4.1"
SENSOR_ENTIDAD = "1.3.6.1.2.1.99.1.1.1"
NOMBRE_ENTIDAD = "1.3.6.1.2.1.47.1.1.1.1.7"

def _lecturas_entidad(datos):
    """Lee sensores estándar: unidades(9), watts(6), rpm(10)."""
    lecturas = {}
    for indice, sensor in filas(datos, {"tipo": SENSOR_ENTIDAD + ".1",
                                         "escala": SENSOR_ENTIDAD + ".2",
                                         "precision": SENSOR_ENTIDAD + ".3",
                                         "valor": SENSOR_ENTIDAD + ".4",
                                         "estado": SENSOR_ENTIDAD + ".5"}):
        nombre = texto(datos.get(NOMBRE_ENTIDAD + "." + str(indice)))
        tipo, escala = numero(sensor.get("tipo")), numero(sensor.get("escala"))
        precision, valor = numero(sensor.get("precision")), numero(sensor.get("valor"))
        if not nombre or tipo not in (6, 10) or escala not in range(1, 18) \
                or precision is None or not 0 <= precision <= 9 or valor is None \
                or numero(sensor.get("estado")) != 1:
            continue
        exponente = (escala - 9) * 3 - precision
        lecturas[nombre] = (tipo, Decimal(valor) * (Decimal(10) ** exponente))
    return lecturas

def _etiqueta_dorado(valor):
    """Solo interpreta campos explícitos del formato simulado de etiqueta electrónica."""
    campos = {}
    for segmento in (texto(valor) or "").split(";"):
        clave, separador, dato = segmento.partition("=")
        clave = clave.strip().upper()
        if separador and clave in ("SN", "MODEL") and dato.strip():
            campos[clave] = dato.strip()
    return campos

def normalizar_storage_huawei(datos, *, fecha_actualizacion):
    d = DORADO
    sensores = _lecturas_entidad(datos)
    disco = d + ".23.5.1.1"
    control = d + ".23.5.2.1"
    power = d + ".23.5.3.1"
    fan = d + ".23.5.4.1"
    discos = []
    for _, f in filas(datos, {"salud": disco + ".2", "tipo": disco + ".5",
                              "mb": disco + ".6", "modelo": disco + ".12",
                              "marca": disco + ".14", "serie": disco + ".15"}):
        discos.append({"numero_serial": texto(f.get("serie")), "marca": texto(f.get("marca")),
            "modelo": texto(f.get("modelo")), "tipo": {14: "NVMe"}.get(numero(f.get("tipo"))),
            "capacidad_gb": dividir(numero(f.get("mb")), 1024), "velocidad_rpm": None,
            "estado": _estado(numero(f.get("salud")))})
    controladoras = []
    for _, f in filas(datos, {"salud": control + ".2", "etiqueta": control + ".17"}):
        etiqueta = _etiqueta_dorado(f.get("etiqueta"))
        controladoras.append({"numero_serial": etiqueta.get("SN"),
                              "modelo": etiqueta.get("MODEL"), "raid": None,
                              "estado": _estado(numero(f.get("salud")))})
    if not discos or not controladoras:
        raise DatosIncompletos("OceanStor no reporta discos y controladoras.")
    salud_controladoras = {indice: _estado(numero(f.get("salud")))
                           for indice, f in filas(datos, {"salud": control + ".2"})}
    cpus = []
    for indice, f in filas(datos, {"info": d + ".19.8.12.1.15"}):
        info = texto(f.get("info"))
        if not info:
            continue
        # El MIB enumera cuatro campos, pero no especifica su separador.
        # Solo se descompone el formato explícito de la muestra; cualquier
        # otro texto se conserva íntegro como modelo.
        partes = [parte.strip() for parte in info.split(";")]
        marca, familia, modelo, velocidad = partes if len(partes) == 4 else (None, None, info, None)
        frecuencia = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(GHz|MHz)", velocidad or "", re.I)
        ghz = (Decimal(frecuencia.group(1).replace(",", ".")) /
               (1000 if frecuencia.group(2).lower() == "mhz" else 1)) if frecuencia else None
        cpus.append({"numero_serial": None, "marca": marca or None,
                     "familia": familia or None, "modelo": modelo or None,
                     "velocidad_ghz": ghz, "cantidad_nucleos": None,
                     "cantidad_hilos": None, "cache_l1_mb": None,
                     "cache_l2_mb": None, "cache_l3_mb": None,
                     "estado": salud_controladoras.get(indice)})
    memoria = []
    for indice, f in filas(datos, {"capacidad_mb": d + ".19.8.12.1.14"}):
        capacidad_mb = numero(f.get("capacidad_mb"))
        if capacidad_mb is None or capacidad_mb <= 0:
            continue
        memoria.append({"numero_serial": None, "marca": None,
                        "modelo": f"Memoria de controladora {indice}",
                        "generacion": None, "velocidad_mhz": None,
                        "capacidad_gb": dividir(capacidad_mb, 1024),
                        "estado": salud_controladoras.get(indice)})
    fuentes = [{"numero_serial": texto(f.get("serie")), "modelo": texto(f.get("modelo")),
                "consumo_w": potencia_nominal_modelo(texto(f.get("modelo"))),
                "tipo_corriente": {0: "DC", 1: "AC"}.get(numero(f.get("tipo"))),
                "estado": _estado(numero(f.get("salud")))}
               for _, f in filas(datos, {"salud": power + ".3", "tipo": power + ".5",
                                         "modelo": power + ".7", "serie": power + ".10"})]
    ventiladores = []
    for indice, f in filas(datos, {"salud": fan + ".3", "etiqueta": fan + ".6"}):
        etiqueta = _etiqueta_dorado(f.get("etiqueta"))
        lectura_rpm = sensores.get(f"Fan {indice} RPM")
        ventiladores.append({"numero_serial": etiqueta.get("SN"),
                             "modelo": etiqueta.get("MODEL"),
                             "velocidad_rpm": lectura_rpm[1] if lectura_rpm and lectura_rpm[0] == 10 else None,
                             "estado": _estado(numero(f.get("salud")))})
    puertos_fc = [{"numero_puerto": texto(f.get("id")) or indice,
                   "mac_address": texto(f.get("wwn")),
                   "velocidad": f"{numero(f['gbps'])} Gbps" if numero(f.get("gbps")) else None,
                   "estado": "Encendido" if numero(f.get("estado")) == 1 else "Apagado"}
                  for indice, f in filas(datos, {"id": d + ".19.8.7.1.3",
                                                    "estado": d + ".19.8.7.1.4",
                                                    "wwn": d + ".19.8.7.1.7",
                                                    "gbps": d + ".19.8.7.1.9"})]
    tarjetas = [{"numero_serial": None, "marca": "Huawei", "modelo": "Fibre Channel",
                 "estado": "Encendido" if any(p["estado"] == "Encendido" for p in puertos_fc) else "Apagado",
                 "cantidad_puertos": len(puertos_fc), "puertos": puertos_fc}] if puertos_fc else []
    total = _n(datos, d + ".1.5.0")
    usado = _n(datos, d + ".1.4.0")
    if total is None or usado is None or usado > total:
        raise DatosIncompletos("La capacidad OceanStor es incompleta o inválida.")
    nodos = filas(datos, {"iops": d + ".21.3.1.5", "latencia": d + ".21.3.1.4"})
    iops = sum(numero(f.get("iops")) or 0 for _, f in nodos) if nodos else None
    latencias = [numero(f.get("latencia")) for _, f in nodos]
    latencia = Decimal(sum(latencias)) / len(latencias) if latencias and all(
        x is not None for x in latencias) else None
    temperaturas = [numero(f.get("temp")) for _, f in filas(datos, {"temp": disco + ".11"})]
    temperaturas = [x for x in temperaturas if x is not None]
    descripcion = _s(datos, "1.3.6.1.2.1.1.1.0")
    modelo = re.search(r"OceanStor\s+Dorado\s+\S+\s+V\d+", descripcion or "", re.I)
    lectura_w = sensores.get("Storage total power")
    consumo = lectura_w[1] if lectura_w and lectura_w[0] == 6 else None
    activo = _base(_s(datos, d + ".1.1.0"), _s(datos, SYSTEM["hostname"]),
                   modelo.group() if modelo else None, "STORAGE",
                   "Encendido" if all(c["estado"] == "Encendido" for c in controladoras) else "Degradado",
                   fecha_actualizacion, firmware=_s(datos, d + ".1.6.0"),
                   temperatura=max(temperaturas) if temperaturas else None,
                   consumo=consumo)
    return {"activo": activo, "storage": {"protocolo_comunicacion": "Fibre Channel",
            "capacidad_total_tb": dividir(total, 1024 ** 2),
            "capacidad_usada_tb": dividir(usado, 1024 ** 2), "iops": iops},
            "componentes": {"cpu": cpus, "disco": discos, "controladora_raid": controladoras,
                            "ram": memoria,
                            "fuente_poder": fuentes, "ventilador": ventiladores,
                            "tarjeta_red": tarjetas},
            "mediciones": _mediciones(activo, (("iops", iops), ("latencia_ms", latencia))),
            "ubicacion_snmp": _s(datos, SYSTEM["ubicacion"])}


def normalizar_storage(datos, *, fecha_actualizacion, fabricante="HPE"):
    perfiles = {"HPE": normalizar_storage_hpe, "Huawei": normalizar_storage_huawei}
    if fabricante not in perfiles:
        raise PerfilNoSoportado("Fabricante de storage sin perfil implementado.")
    return perfiles[fabricante](datos, fecha_actualizacion=fecha_actualizacion)
