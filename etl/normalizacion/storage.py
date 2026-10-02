"""Ficha de arreglo Fibre Channel y componentes HPE documentados."""
import re
from etl.errores import DatosIncompletos
from etl.oid_util import SYSTEM, filas, texto, numero
from etl.normalizacion.servidor import normalizar_servidor_hpe
from etl.normalizacion.reglas import mb_a_gb, dividir
from etl.normalizacion.estados import CONDICION_HPE, normalizar_estado

SS="1.3.6.1.4.1.232.8.2.2.1.1"
FC="1.3.6.1.4.1.232.16.2"
NIM="1.3.6.1.4.1.37447.1.3"
RAID={2:"RAID0",3:"RAID1",4:"RAID4",5:"RAID5",7:"RAID6"}
CTRL={3:"MSA1000",6:"HSV110"}
HBA={58:"HPE FCA LPe1605",85:"HPE FCA SN1600E 2P"}

def normalizar_storage(datos, *, fecha_actualizacion):
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
            "marca":None,"tipo":{2:"SCSI",3:"SATA",4:"SAS"}.get(numero(d.get("tipo"))),
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
