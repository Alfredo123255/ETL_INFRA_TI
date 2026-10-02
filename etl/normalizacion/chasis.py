"""Ficha de chasis blade HPE y sus slots, energía e interconexiones."""
import re
from etl.errores import DatosIncompletos
from etl.oid_util import SYSTEM, filas, texto, numero
from etl.normalizacion.estados import CONDICION_HPE, normalizar_estado

BASE="1.3.6.1.4.1.232.22.2"
C=BASE+".3.1.1.1"
S=BASE+".4.1.1.1"
F=BASE+".3.1.3.1"
P=BASE+".5.1.1.1"
N=BASE+".6.1.1.1"
IF="1.3.6.1.2.1.2.2.1"
IFX="1.3.6.1.2.1.31.1.1.1"

def normalizar_chasis(datos, *, fecha_actualizacion):
    enclosures=filas(datos,{"modelo":C+".3","serie":C+".7","firmware":C+".8",
                            "hostname":C+".9","estado":C+".16"})
    if len(enclosures)!=1:
        raise DatosIncompletos("El chasis no proporciona una identidad única.")
    e=enclosures[0][1]
    serie,modelo=texto(e.get("serie")),texto(e.get("modelo"))
    hostname=texto(e.get("hostname")) or texto(datos.get(SYSTEM["hostname"]))
    if not serie or not modelo or not hostname:
        raise DatosIncompletos("Falta hostname, serie o modelo del chasis.")
    slots=[]
    for _,s in filas(datos,{"numero_slot":S+".8","presente":S+".12", "estado":S+".21", "hostname":S+".4"}):
        present=numero(s.get("presente")); state=numero(s.get("estado"))
        status="LIBRE" if present!=3 else "OCUPADO" if state==2 else "DEGRADADO"
        slots.append({"numero_slot":numero(s.get("numero_slot")),"estado":status,
            "hostname_servidor":texto(s.get("hostname")) if status!="LIBRE" else None})
    capacity=filas(datos,{"max":BASE+".3.2.1.1.4"})
    max_slots=numero(capacity[0][1].get("max")) if capacity else None
    if max_slots is None or max_slots<len(slots) or not slots:
        raise DatosIncompletos("La capacidad de slots del chasis es inválida.")
    fans=[]
    for _,f in filas(datos,{"modelo":F+".6","estado":F+".11"}):
        fans.append({"numero_serial":None,"modelo":texto(f.get("modelo")),"velocidad_rpm":None,
            "estado":normalizar_estado(numero(f.get("estado")),CONDICION_HPE)})
    fuentes=[]
    for _,f in filas(datos,{"serie":P+".5","modelo":P+".6","consumo":P+".10","estado":P+".17"}):
        fuentes.append({"numero_serial":texto(f.get("serie")),"modelo":texto(f.get("modelo")),
            "consumo_w":numero(f.get("consumo")),"tipo_corriente":None,
            "estado":normalizar_estado(numero(f.get("estado")),CONDICION_HPE)})
    network=[]
    interfaces={}
    for idx,port in filas(datos,{"name":IFX+".1","speed":IFX+".15","oper":IF+".8"}):
        ifname=texto(port.get("name"))
        if ifname and re.fullmatch(r"[Xd]\d+",ifname):
            interfaces[idx]={"numero_puerto":ifname,"mac_address":None,
                "velocidad":f"{numero(port['speed'])} Mbps" if numero(port.get("speed")) else None,
                "estado":"Encendido" if numero(port.get("oper"))==1 else "Apagado"}
    for index,(_,n) in enumerate(filas(datos,{"modelo":N+".6","serie":N+".7","presente":N+".11"})):
        # El simulador sólo atribuye puertos IF-MIB al primer módulo Virtual Connect.
        ports=list(interfaces.values()) if index==0 else []
        network.append({"numero_serial":texto(n.get("serie")),"marca":None,"modelo":texto(n.get("modelo")),
            "estado":"Encendido" if numero(n.get("presente"))==3 else "Apagado",
            "cantidad_puertos":len(ports),"puertos":ports})
    temps=filas(datos,{"valor":BASE+".3.1.2.1.6"})
    temperature=numero(temps[0][1].get("valor")) if temps else None
    meters=filas(datos,{"watts":BASE+".5.2.1.1.8"})
    power=numero(meters[0][1].get("watts")) if meters else None
    gen=re.search(r"\bG\d+\b",modelo,re.I)
    activo={"numero_serie":serie,"hostname":hostname,"fabricante":"HPE","modelo":modelo,
        "generacion":gen.group() if gen else None,"tipo_activo":"CHASIS",
        "estado_operativo":normalizar_estado(numero(e.get("estado")),CONDICION_HPE),
        "version_firmware":texto(e.get("firmware")),"ultima_actualizacion":fecha_actualizacion,
        "temperatura":temperature,"consumo_electrico_w":power}
    mediciones=[{"nombre_metrica":name,"valor":value} for name,value in
        (("temperatura",temperature),("consumo_electrico_w",power)) if value is not None]
    return {"activo":activo,"chasis_blade":{"cantidad_slots":max_slots},
        "componentes":{"chasis_slot":slots,"ventilador":fans,"fuente_poder":fuentes,"tarjeta_red":network},
        "mediciones":mediciones,"ubicacion_snmp":texto(datos.get(SYSTEM["ubicacion"]))}
