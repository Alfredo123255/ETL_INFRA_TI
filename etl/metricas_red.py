"""Tasas de red por puerto mediante dos consultas SNMP SHA/AES dentro del ciclo.

Contadores de 64 bits preferidos; no guarda contadores como métricas ni crea tablas.
"""
import asyncio
import re
from decimal import Decimal
from time import monotonic
from etl.oid_util import filas, numero, texto
from etl.snmp_cliente import SesionSNMP

IF = "1.3.6.1.2.1.2.2.1"
IFX = "1.3.6.1.2.1.31.1.1.1"
CPQ = "1.3.6.1.4.1.232.18.2.3.1.1"
UPTIME = "1.3.6.1.2.1.1.3.0"


def interfaces(datos, tipo):
    """Selecciona interfaces físicas; evita sumar VLAN, loopback o agregaciones."""
    resultado = []
    for indice, f in filas(datos, {"tipo": IF+".3", "nombre": IFX+".1",
            "nombre_corto": IF+".2", "mbps": IFX+".15", "bps": IF+".5",
            "hc_in": IFX+".6", "hc_out": IFX+".10", "in": IF+".10", "out": IF+".16"}):
        if numero(f.get("tipo")) not in (6, 56):
            continue
        if tipo == "SWITCH" and (numero(f.get("tipo")) != 6 or
                not re.fullmatch(r"\d+/\d+/\d+", texto(f.get("nombre")) or "")):
            continue
        hc = numero(f.get("hc_in")) is not None and numero(f.get("hc_out")) is not None
        mbps = numero(f.get("mbps"))
        bps = numero(f.get("bps"))
        velocidad = Decimal(mbps) if mbps and mbps > 0 else (
            Decimal(bps)/1000000 if bps and 0 < bps < 4294967295 else None)
        resultado.append({"id": "if:"+indice,
            "etiqueta": texto(f.get("nombre")) or texto(f.get("nombre_corto")) or indice,
            "tipo": "puerto_switch" if tipo == "SWITCH" else "puerto_tarjeta_red",
            "velocidad": velocidad, "bits": 64 if hc else 32,
            "entrada": (IFX+".6." if hc else IF+".10.")+indice,
            "salida": (IFX+".10." if hc else IF+".16.")+indice,
            "oper": IF+".8."+indice, "disc": IFX+".19."+indice,
            "nombre_oid": IFX+".1."+indice,
            "tiene_contadores": hc or (numero(f.get("in")) is not None and numero(f.get("out")) is not None)})
    if resultado or tipo == "SWITCH":
        return resultado
    # CPQNIC es el respaldo para servidores HPE que no ofrecen IF-MIB.
    for indice, f in filas(datos, {"mbps": CPQ+".36", "bps": CPQ+".33",
            "puerto": CPQ+".10", "slot": CPQ+".5", "in": CPQ+".37", "out": CPQ+".38"}):
        mbps, bps = numero(f.get("mbps")), numero(f.get("bps"))
        velocidad = Decimal(mbps) if mbps and mbps > 0 else (
            Decimal(bps)/1000000 if bps and 0 < bps < 4294967295 else None)
        resultado.append({"id": "cpqnic:"+indice, "etiqueta": indice,
            "tipo": "puerto_tarjeta_red", "velocidad": velocidad, "bits": 32,
            "entrada": CPQ+".37."+indice, "salida": CPQ+".38."+indice,
            "oper": CPQ+".14."+indice, "disc": None, "nombre_oid": None,
            "tiene_contadores": numero(f.get("in")) is not None and numero(f.get("out")) is not None})
    return resultado


def calcular(puerto, anterior, actual):
    segundos = Decimal(str(actual["tiempo"] - anterior["tiempo"]))
    if segundos <= 0:
        return {}
    for campo in ("discontinuidad", "nombre"):
        if anterior.get(campo) != actual.get(campo):
            return {}
    if anterior.get("uptime") is not None and actual.get("uptime") is not None and actual["uptime"] < anterior["uptime"]:
        return {}
    esperado = 2 if puerto["id"].startswith("cpqnic:") else 1
    if anterior.get("oper") != esperado or actual.get("oper") != esperado:
        return {}
    bits, velocidad = puerto["bits"], puerto.get("velocidad")
    # Sin velocidad no puede descartarse más de una vuelta de Counter32.
    if bits == 32 and (not velocidad or velocidad * 1000000 * segundos / 8 >= 2**32):
        return {}
    valores = {}
    for campo, nombre in (("entrada", "red_trafico_entrada_mbps"),
                          ("salida", "red_trafico_salida_mbps")):
        a, b = anterior.get(campo), actual.get(campo)
        if a is None or b is None or not 0 <= a < 2**bits or not 0 <= b < 2**bits:
            continue
        delta = b - a
        if delta < 0:
            # Solo aceptar una vuelta si hay un marcador fiable sin reinicio.
            if bits == 64 or anterior.get("discontinuidad") is None or actual.get("uptime") is None:
                continue
            delta += 2**bits
        tasa = Decimal(delta) * 8 / segundos / 1000000
        valores[nombre] = tasa
    if velocidad and len(valores) == 2:
        utilizacion = max(valores.values()) / velocidad * 100
        if utilizacion <= 100:
            valores["red_utilizacion_pct"] = utilizacion
    return valores


async def agregar_metricas_red(ficha, datos, conexion):
    tipo = ficha["activo"]["tipo_activo"]
    puertos = interfaces(datos, tipo)
    if tipo == "SWITCH":
        inventariados = {p["numero_puerto"] for p in ficha.get("componentes", {}).get("puerto_switch", [])}
        puertos = [p for p in puertos if p["etiqueta"] in inventariados]
    mediciones = ficha.setdefault("mediciones", [])
    if not puertos and tipo != "SWITCH":
        # Puertos FC sin IF-MIB: la ficha ya normalizó la velocidad del MIB.
        for tarjeta in ficha.get("componentes", {}).get("tarjeta_red", []):
            for p in tarjeta.get("puertos", []):
                velocidad = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(Mbps|Gbps)", p.get("velocidad") or "")
                if velocidad:
                    mbps = Decimal(velocidad.group(1)) * (1000 if velocidad.group(2) == "Gbps" else 1)
                    identificador = p.get("mac_address") or p.get("numero_puerto")
                    if mbps > 0 and identificador is not None:
                        mediciones.append({"nombre_metrica": "red_ancho_banda_mbps", "valor": mbps,
                            "componente_tipo": "puerto_tarjeta_red", "componente_serial": "puerto:"+str(identificador)})

    for p in puertos:
        if p["velocidad"] is not None:
            mediciones.append({"nombre_metrica": "red_ancho_banda_mbps", "valor": p["velocidad"],
                "componente_tipo": p["tipo"], "componente_serial": p["etiqueta"] if tipo == "SWITCH" else p["id"]})
    muestreados = [p for p in puertos if p["tiene_contadores"]]
    if not muestreados:
        return

    async def consultar(sesion):
        resultado = {}
        for p in muestreados:
            oids = [p["entrada"], p["salida"], p["oper"], UPTIME]
            oids.extend(x for x in (p["disc"], p["nombre_oid"]) if x)
            inicio = monotonic()
            valores = await sesion.obtener(oids)
            resultado[p["id"]] = {"tiempo": (inicio + monotonic())/2,
                "entrada": numero(valores.get(p["entrada"])), "salida": numero(valores.get(p["salida"])),
                "oper": numero(valores.get(p["oper"])), "uptime": numero(valores.get(UPTIME)),
                "discontinuidad": numero(valores.get(p["disc"])) if p["disc"] else None,
                "nombre": texto(valores.get(p["nombre_oid"])) if p["nombre_oid"] else None}
        return resultado

    with SesionSNMP(conexion) as sesion:
        anterior = await consultar(sesion)
        await asyncio.sleep(1)
        actual = await consultar(sesion)
    for p in muestreados:
        for nombre, valor in calcular(p, anterior[p["id"]], actual[p["id"]]).items():
            mediciones.append({"nombre_metrica": nombre, "valor": valor,
                "componente_tipo": p["tipo"], "componente_serial": p["etiqueta"] if tipo == "SWITCH" else p["id"]})
