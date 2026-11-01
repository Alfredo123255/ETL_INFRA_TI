"""Rendimiento HPE simulado: operaciones, bytes y tiempo de servicio acumulados."""
import asyncio
from decimal import Decimal, ROUND_HALF_UP
from time import monotonic
from etl.snmp_cliente import SesionSNMP
from etl.oid_util import numero

BASE="1.3.6.1.4.1.37447.1.3"
UPTIME="1.3.6.1.2.1.1.3.0"
COLUMNAS=(2,4,6,7,8,10)


def calcular(anterior,actual):
    segundos=Decimal(str(actual["tiempo"]-anterior["tiempo"]))
    if segundos<=0:return {}
    if anterior.get("uptime") is not None and actual.get("uptime") is not None and actual["uptime"]<anterior["uptime"]:return {}
    delta={}
    for c in COLUMNAS:
        a,b=anterior.get(c),actual.get(c)
        if a is None or b is None or not 0<=a<=b<2**64:return {}
        delta[c]=Decimal(b-a)
    operaciones=delta[2]+delta[4]
    valores={"almacenamiento_iops":operaciones/segundos,
        "almacenamiento_throughput_lectura_mbps":delta[8]*8/segundos/1000000,
        "almacenamiento_throughput_escritura_mbps":delta[10]*8/segundos/1000000}
    if operaciones>0:
        valores["almacenamiento_latencia_ms"]=(delta[6]+delta[7])/operaciones/1000
    return valores


async def agregar_metricas_storage(ficha,datos,conexion):
    if ficha["activo"]["tipo_activo"]!="STORAGE" or ficha["activo"]["fabricante"]!="HPE":return
    oids=[f"{BASE}.{c}.0" for c in COLUMNAS]
    if not all(oid in datos for oid in oids):return
    async def consultar(sesion):
        inicio=monotonic()
        valores=await sesion.obtener([*oids,UPTIME])
        return {"tiempo":(inicio+monotonic())/2,"uptime":numero(valores.get(UPTIME)),
                **{c:numero(valores.get(f"{BASE}.{c}.0")) for c in COLUMNAS}}
    with SesionSNMP(conexion) as sesion:
        antes=await consultar(sesion)
        await asyncio.sleep(1)
        despues=await consultar(sesion)
    valores=calcular(antes,despues)
    ficha["mediciones"].extend({"nombre_metrica":n,"valor":v} for n,v in valores.items())
    if "almacenamiento_iops" in valores:
        ficha["storage"]["iops"]=int(valores["almacenamiento_iops"].to_integral_value(rounding=ROUND_HALF_UP))
