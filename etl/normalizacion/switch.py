"""Ficha ArubaOS-CX desde MIB propietaria, IF-MIB y componentes simulados."""
import re
from etl.errores import DatosIncompletos
from etl.oid_util import SYSTEM, filas, texto, numero
from etl.normalizacion.reglas import mhz_a_ghz, kb_a_gb, dividir
from etl.normalizacion.estados import CONDICION_HPE, ESTADO_RAM_HPE, normalizar_estado
from etl.oids.servidor import OIDS_CPU, OIDS_CACHE, OIDS_RAM
from etl.normalizacion.servidor import MARCAS_CPU

P = "1.3.6.1.4.1.47196.4.1.1.3"
MOD = P + ".11.6.1.1"
PSU = P + ".11.2.1.1"
FAN = P + ".11.5.1.1"
TEMP = P + ".11.3.1.1"
IF = "1.3.6.1.2.1.2.2.1"
IFX = "1.3.6.1.2.1.31.1.1.1"

def estado_texto(value):
    value = (texto(value) or "").lower()
    if value in ("ok", "normal", "enabled", "up"):
        return "Encendido"
    if value in ("fault", "failed", "down", "empty", "absent"):
        return "Apagado"
    return "Degradado"

def normalizar_switch(datos, *, fecha_actualizacion):
    modules = filas(datos, {"modelo": MOD+".7", "serie": MOD+".8", "estado": MOD+".6"})
    if len(modules) != 1:
        raise DatosIncompletos("El switch no proporciona una identidad de chasis única.")
    m = modules[0][1]
    hostname = texto(datos.get(SYSTEM["hostname"]))
    serie, modelo = texto(m.get("serie")), texto(m.get("modelo"))
    if not hostname or not serie or not modelo:
        raise DatosIncompletos("Falta hostname, serie o modelo del switch.")
    puertos = []
    cols = {"tipo": IF+".3", "admin": IF+".7", "oper": IF+".8",
            "nombre": IFX+".1", "velocidad": IFX+".15"}
    for _, row in filas(datos, cols):
        nombre = texto(row.get("nombre"))
        if numero(row.get("tipo")) != 6 or not nombre or not re.fullmatch(r"\d+/\d+/\d+", nombre):
            continue
        mbps = numero(row.get("velocidad"))
        puertos.append({"numero_puerto": nombre,
            "velocidad": f"{mbps} Mbps" if mbps and mbps > 0 else None,
            "estado": "Encendido" if numero(row.get("admin")) == 1 and numero(row.get("oper")) == 1 else "Apagado"})
    if not puertos:
        raise DatosIncompletos("El switch no reporta puertos físicos.")
    fans = []
    for _, row in filas(datos, {"modelo": FAN+".6", "serie": FAN+".7", "rpm": FAN+".8", "estado": FAN+".10"}):
        state = numero(row.get("estado"))
        fans.append({"numero_serial": texto(row.get("serie")), "modelo": texto(row.get("modelo")),
            "velocidad_rpm": numero(row.get("rpm")),
            "estado": {4:"Encendido",5:"Apagado",1:"Degradado",2:"Apagado",3:"Degradado"}.get(state,"Degradado")})
    fuentes = []
    for _, row in filas(datos, {"modelo": PSU+".5", "serie": PSU+".6", "consumo": PSU+".7", "estado": PSU+".11"}):
        state = numero(row.get("estado"))
        fuentes.append({"numero_serial": texto(row.get("serie")), "modelo": texto(row.get("modelo")),
            "consumo_w": numero(row.get("consumo")), "tipo_corriente": None,
            "estado": "Encendido" if state == 1 else "Degradado" if state in (7,10,11) else "Apagado"})
    temperatures = filas(datos, {"nombre": TEMP+".5", "valor": TEMP+".7"})
    temp = next((dividir(numero(r.get("valor")),1000) for _,r in temperatures
                 if texto(r.get("nombre")) == "Chassis-Ambient"), None)
    if temp is None and temperatures:
        temp = dividir(numero(temperatures[0][1].get("valor")),1000)
    consumed = numero(datos.get(P+".11.8.1.0.1.1.6.1.0.1"))
    firmware = texto(datos.get(P+".26.1.1.1.1.3.1"))
    gen = re.search(r"\b6300M\b",modelo)
    cpu=[]
    caches=filas(datos,OIDS_CACHE)
    for indice,r in filas(datos,OIDS_CPU):
        nucleos=numero(r.get("cantidad_nucleos"))
        threads=numero(r.get("hilos_por_nucleo"))
        entry={"numero_serial":texto(r.get("numero_serial")),"familia":None,
            "marca":MARCAS_CPU.get(numero(r.get("marca"))),"modelo":texto(r.get("modelo")),
            "velocidad_ghz":mhz_a_ghz(numero(r.get("velocidad_mhz"))),
            "cantidad_nucleos":nucleos,
            "cantidad_hilos":nucleos*threads if nucleos is not None and threads is not None else None,
            "estado":normalizar_estado(numero(r.get("estado")),CONDICION_HPE)}
        for level in (1,2,3):
            sizes=[numero(c.get("capacidad_kb")) for i,c in caches
                   if i.split(".")[0]==indice.split(".")[0] and numero(c.get("nivel"))==level]
            entry[f"cache_l{level}_mb"]=dividir(sum(x for x in sizes if x is not None),1024) if sizes else None
        cpu.append(entry)
    ram=[]
    for _,r in filas(datos,OIDS_RAM):
        ram.append({"numero_serial":texto(r.get("numero_serial")),"marca":texto(r.get("marca")),
            "modelo":texto(r.get("modelo")),"generacion":None,"velocidad_mhz":numero(r.get("velocidad_mhz")),
            "capacidad_gb":kb_a_gb(numero(r.get("capacidad_kb"))),
            "estado":normalizar_estado(numero(r.get("estado")),ESTADO_RAM_HPE)})
    system_info=P+".22.1.0.1.1"
    mediciones=[]
    for col,name in ((3,"cpu_uso_pct"),(4,"ram_uso_pct")):
        value=next((numero(v) for oid,v in datos.items() if oid.startswith(system_info+f".{col}.")),None)
        if value is not None: mediciones.append({"nombre_metrica":name,"valor":value})
    activo={"numero_serie":serie,"hostname":hostname,"fabricante":"HPE Aruba Networking",
        "modelo":modelo,"generacion":gen.group() if gen else None,"tipo_activo":"SWITCH",
        "estado_operativo":estado_texto(m.get("estado")),"version_firmware":firmware,
        "ultima_actualizacion":fecha_actualizacion,"temperatura":temp,"consumo_electrico_w":consumed}
    for name,value in (("temperatura",temp),("consumo_electrico_w",consumed)):
        if value is not None:mediciones.append({"nombre_metrica":name,"valor":value})
    return {"activo":activo,"switch":{"tipo_red":None,"modo_operacion":None,
        "cantidad_puertos":len(puertos),"cantidad_puertos_ocupados":sum(p["estado"]=="Encendido" for p in puertos)},
        "componentes":{"puerto_switch":puertos,"fuente_poder":fuentes,"ventilador":fans,"cpu":cpu,"ram":ram},
        "mediciones":mediciones,"ubicacion_snmp":texto(datos.get(SYSTEM["ubicacion"]))}
