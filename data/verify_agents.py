#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de verificacion de los agentes SNMPv3 simulados hpe-dl380-01,
hpe-dl360-01, hpe-c7000-01, hpe-bl460c-01, hpe-bl460c-02, aruba-cx-sw01,
hpe-storage-fc-01 y hpe-storage-fc-02.

Hace un GET contra sysDescr.0 y contra 2-4 OID mapeados (ver
mibs/hpe-real/MAPEO-SERVIDOR.md, mibs/hpe-real/MAPEO-CHASIS.md,
mibs/ALL-Supported-MIBs/MAPEO-SWITCH.md y mibs/hpe-real/MAPEO-STORAGE.md)
de cada agente, usando el patron UsmUserData/ContextData de pysnmp para
autenticacion SNMPv3 (auth=SHA, priv=AES). Al final, hace dos GET seguidos
(con una pausa corta entre medio) sobre un contador Counter32 (cpqnic, en
un servidor rack), dos Counter64 (ifHCInOctets en el chasis y en
aruba-cx-sw01) y los contadores Counter64 de NIMBLE-MIB (globalStats) de
las dos unidades de storage, para comprobar que los valores crecen
(variacion `numeric` de snmpsim) y para calcular IOPS/latencia en vivo.

Uso: python data/verify_agents.py
"""
import asyncio
import os
import time

from pysnmp.hlapi.asyncio import (
    CommunityData,  # noqa: F401  (no usado, referencia para lectura)
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    nextCmd,
    usmAesCfb128Protocol,
    usmHMACSHAAuthProtocol,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Credenciales y OID por agente (ver data/*/README.md) -------------
AGENTS = [
    {
        "nombre": "hpe-dl380-01",
        "host": "127.0.0.11",
        "puerto": 16100,
        "usuario": "monitor_dl380",
        "auth_key": "Kr7aY5nT2LdUco2B5IAZ",
        "priv_key": "GpoJkRAhPOZg3vA4qHyT",
        "oids": [
            ("sysDescr.0", "1.3.6.1.2.1.1.1.0"),
            ("hostname (cpqHoSystemName.0)", "1.3.6.1.4.1.232.11.2.2.12.0"),
            ("numero_serie (cpqSiSysSerialNum.0)", "1.3.6.1.4.1.232.2.2.2.1.0"),
            ("consumo_electico_w (cpqHePowerMeterCurrReading.0)", "1.3.6.1.4.1.232.6.2.15.3.0"),
            ("mac_address NIC2 (cpqNicIfPhysAdapterMACAddress.2)", "1.3.6.1.4.1.232.18.2.3.1.1.4.2"),
            ("ip_sistema_operativo (ipAdEntAddr)", "1.3.6.1.2.1.4.20.1.1.10.10.12.11"),
        ],
    },
    {
        "nombre": "hpe-dl360-01",
        "host": "127.0.0.12",
        "puerto": 16200,
        "usuario": "monitor_dl360",
        "auth_key": "3nRFCWnSuDougjTVD3SV",
        "priv_key": "Wru30SG1uouCjtcd5h7P",
        "oids": [
            ("sysDescr.0", "1.3.6.1.2.1.1.1.0"),
            ("hostname (cpqHoSystemName.0)", "1.3.6.1.4.1.232.11.2.2.12.0"),
            ("estado_operativo (cpqHeMibCondition.0)", "1.3.6.1.4.1.232.6.1.3.0"),
            ("temperatura sensor 1 (cpqHeTemperatureCelsius.1.1)", "1.3.6.1.4.1.232.6.2.6.8.1.4.1.1"),
            ("estado puerto NIC2 caido (cpqNicIfPhysAdapterStatus.2)", "1.3.6.1.4.1.232.18.2.3.1.1.14.2"),
        ],
    },
    {
        "nombre": "hpe-c7000-01",
        "host": "127.0.0.15",
        "puerto": 16300,
        "usuario": "monitor_c7000",
        "auth_key": "cy8EcO4BePPAN9Os5zts",
        "priv_key": "NR2yILtdOtWShA70stgf",
        "oids": [
            ("sysDescr.0", "1.3.6.1.2.1.1.1.0"),
            ("hostname (cpqRackCommonEnclosureName.1.1)", "1.3.6.1.4.1.232.22.2.3.1.1.1.9.1.1"),
            ("cantidad_slots (cpqRackServerEnclosureMaxNumBlades.1.1)", "1.3.6.1.4.1.232.22.2.3.2.1.1.4.1.1"),
            ("chasisSlots[1].hostanameServidor (cpqRackServerBladeName.1.1.1)", "1.3.6.1.4.1.232.22.2.4.1.1.1.4.1.1.1"),
            ("puerto X1 (ifName.1)", "1.3.6.1.2.1.31.1.1.1.1.1"),
            ("vcModulePortIfIndex puerto 1", "1.3.6.1.4.1.11.5.7.5.2.3.1.1.6.1.2.1"),
        ],
    },
    {
        "nombre": "hpe-bl460c-01",
        "host": "127.0.0.13",
        "puerto": 16400,
        "usuario": "monitor_bl460c01",
        "auth_key": "Yb2QzP9mLxT4wVh8Kd3R",
        "priv_key": "Ft6NcE1oRgJ5sWp2Ux9M",
        "oids": [
            ("sysDescr.0", "1.3.6.1.2.1.1.1.0"),
            ("hostname (cpqHoSystemName.0)", "1.3.6.1.4.1.232.11.2.2.12.0"),
            ("numero_serie (cpqSiSysSerialNum.0)", "1.3.6.1.4.1.232.2.2.2.1.0"),
            ("serie controladora RAID (cpqDaCntlrSerialNumber.1)", "1.3.6.1.4.1.232.3.2.2.1.1.15.1"),
            ("ip_sistema_operativo (ipAdEntAddr)", "1.3.6.1.2.1.4.20.1.1.10.10.12.13"),
        ],
    },
    {
        "nombre": "hpe-bl460c-02",
        "host": "127.0.0.14",
        "puerto": 16500,
        "usuario": "monitor_bl460c02",
        "auth_key": "Ht4RxQ8kMbZ3vNp6Ld1J",
        "priv_key": "Sc9WjE2yTfL7uKq4Gz5V",
        "oids": [
            ("sysDescr.0", "1.3.6.1.2.1.1.1.0"),
            ("hostname (cpqHoSystemName.0)", "1.3.6.1.4.1.232.11.2.2.12.0"),
            ("numero_serie (cpqSiSysSerialNum.0)", "1.3.6.1.4.1.232.2.2.2.1.0"),
            ("serie modulo RAM 1 (cpqSiMemModuleSerialNo.0.1)", "1.3.6.1.4.1.232.2.2.4.5.1.10.0.1"),
            ("ip_sistema_operativo (ipAdEntAddr)", "1.3.6.1.2.1.4.20.1.1.10.10.12.14"),
        ],
    },
    {
        "nombre": "aruba-cx-sw01",
        "host": "127.0.0.20",
        "puerto": 16600,
        "usuario": "monitor_sw01",
        "auth_key": "2JePukZ17WBQg10i3J3U",
        "priv_key": "ZynkEa6RTaPcFsqG1Oc5",
        "oids": [
            ("sysDescr.0", "1.3.6.1.2.1.1.1.0"),
            ("sysObjectID.0 (identidad JL661A)", "1.3.6.1.2.1.1.2.0"),
            ("numero_serie (arubaWiredModuleSerialNumber)", "1.3.6.1.4.1.47196.4.1.1.3.11.6.1.1.8.1.1.1"),
            ("version_firmware (arubaWiredSwitchImageVersion.1)", "1.3.6.1.4.1.47196.4.1.1.3.26.1.1.1.1.3.1"),
            ("temperatura ambiente (arubaWiredTempSensorTemperature)", "1.3.6.1.4.1.47196.4.1.1.3.11.3.1.1.7.1.1.1.1"),
            ("estado puerto 48 admin down (ifAdminStatus)", "1.3.6.1.2.1.2.2.1.7.48"),
        ],
    },
    {
        "nombre": "hpe-storage-fc-01",
        "host": "127.0.0.30",
        "puerto": 16700,
        "usuario": "monitor_storagefc01",
        "auth_key": "RcVQ87sKGKNAXteaPhvF",
        "priv_key": "87KIBACIxZCukpKjai0Z",
        "oids": [
            ("sysDescr.0", "1.3.6.1.2.1.1.1.0"),
            ("array serial (cpqSsChassisSerialNumber.1)", "1.3.6.1.4.1.232.8.2.2.1.1.3.1"),
            ("disco 6 degradado (cpqFcaPhyDrvCondition)", "1.3.6.1.4.1.232.16.2.5.1.1.31.1.6"),
            ("capacidad_usada low (diskVolBytesUsedLow, PRESTADO Nimble)", "1.3.6.1.4.1.37447.1.3.12.0"),
        ],
    },
    {
        "nombre": "hpe-storage-fc-02",
        "host": "127.0.0.31",
        "puerto": 16800,
        "usuario": "monitor_storagefc02",
        "auth_key": "SMkMLpmciBdaLR9pfDux",
        "priv_key": "2VcFacU3YHQ1CqwgAg7D",
        "oids": [
            ("sysDescr.0", "1.3.6.1.2.1.1.1.0"),
            ("PSU2 failed (cpqHeFltTolPowerSupplyCondition)", "1.3.6.1.4.1.232.6.2.9.3.1.4.1.2"),
            ("RAID faultTol mirroring (cpqFcaLogDrvFaultTol)", "1.3.6.1.4.1.232.16.2.3.1.1.3.1.1"),
            ("IOPS lectura acumuladas (ioReads, PRESTADO Nimble)", "1.3.6.1.4.1.37447.1.3.2.0"),
        ],
    },
]

# --- OID de contadores crecientes (variacion `numeric` de snmpsim) -----
CONTADOR_COUNTER32 = {
    "agente": "hpe-dl380-01",
    "host": "127.0.0.11",
    "puerto": 16100,
    "usuario": "monitor_dl380",
    "auth_key": "Kr7aY5nT2LdUco2B5IAZ",
    "priv_key": "GpoJkRAhPOZg3vA4qHyT",
    "etiqueta": "cpqNicIfPhysAdapterInOctets.2 (Counter32, tag 65)",
    "oid": "1.3.6.1.4.1.232.18.2.3.1.1.37.2",
}

CONTADOR_COUNTER64 = {
    "agente": "hpe-c7000-01",
    "host": "127.0.0.15",
    "puerto": 16300,
    "usuario": "monitor_c7000",
    "auth_key": "cy8EcO4BePPAN9Os5zts",
    "priv_key": "NR2yILtdOtWShA70stgf",
    "etiqueta": "ifHCInOctets puerto X1 (Counter64, tag 70)",
    "oid": "1.3.6.1.2.1.31.1.1.1.6.1",
}

CONTADOR_COUNTER64_SWITCH = {
    "agente": "aruba-cx-sw01",
    "host": "127.0.0.20",
    "puerto": 16600,
    "usuario": "monitor_sw01",
    "auth_key": "2JePukZ17WBQg10i3J3U",
    "priv_key": "ZynkEa6RTaPcFsqG1Oc5",
    "etiqueta": "ifHCInOctets puerto 1/1/49 up (Counter64, tag 70)",
    "oid": "1.3.6.1.2.1.31.1.1.1.6.49",
}


async def consultar_agente(agente):
    print(f"\n=== {agente['nombre']} ({agente['host']}:{agente['puerto']}) ===")

    snmpEngine = SnmpEngine()
    authData = UsmUserData(
        agente["usuario"],
        authKey=agente["auth_key"],
        privKey=agente["priv_key"],
        authProtocol=usmHMACSHAAuthProtocol,
        privProtocol=usmAesCfb128Protocol,
    )
    transportTarget = UdpTransportTarget(
        (agente["host"], agente["puerto"]), timeout=3, retries=1
    )
    # snmpsim-command-responder registra sus datos bajo el contexto "public"
    # (ver el log de arranque del agente: "SNMPv3 Context Name: ... or public").
    # Sin este contextName explicito, el agente descarta la solicitud
    # silenciosamente tras descifrarla (no encuentra el "contexto" vacio).
    contextData = ContextData(contextName="public")

    for etiqueta, oid in agente["oids"]:
        objType = ObjectType(ObjectIdentity(oid))
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            snmpEngine, authData, transportTarget, contextData, objType
        )

        if errorIndication:
            print(f"  [ERROR] {etiqueta} ({oid}): {errorIndication}")
        elif errorStatus:
            print(
                f"  [ERROR] {etiqueta} ({oid}): {errorStatus.prettyPrint()} en "
                f"{varBinds[int(errorIndex) - 1][0] if errorIndex else '?'}"
            )
        else:
            for varBind in varBinds:
                nombre, valor = varBind
                print(f"  {etiqueta:55s} = {valor.prettyPrint()}")

    snmpEngine.closeDispatcher()


async def _get_valor(cfg, oid):
    snmpEngine = SnmpEngine()
    authData = UsmUserData(
        cfg["usuario"],
        authKey=cfg["auth_key"],
        privKey=cfg["priv_key"],
        authProtocol=usmHMACSHAAuthProtocol,
        privProtocol=usmAesCfb128Protocol,
    )
    transportTarget = UdpTransportTarget((cfg["host"], cfg["puerto"]), timeout=3, retries=1)
    contextData = ContextData(contextName="public")
    objType = ObjectType(ObjectIdentity(oid))

    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
        snmpEngine, authData, transportTarget, contextData, objType
    )
    snmpEngine.closeDispatcher()

    if errorIndication or errorStatus:
        raise RuntimeError(f"{errorIndication or errorStatus} en {oid}")

    return int(varBinds[0][1])


async def probar_contadores_crecientes():
    print("\n=== Prueba de contadores crecientes (dos GET seguidos) ===")

    for cfg in (CONTADOR_COUNTER32, CONTADOR_COUNTER64, CONTADOR_COUNTER64_SWITCH):
        print(f"\n  {cfg['agente']}: {cfg['etiqueta']} ({cfg['oid']})")
        try:
            valor1 = await _get_valor(cfg, cfg["oid"])
            print(f"    GET 1 = {valor1}")
            time.sleep(3)
            valor2 = await _get_valor(cfg, cfg["oid"])
            print(f"    GET 2 = {valor2}  (delta = +{valor2 - valor1})")
            if valor2 > valor1:
                print("    [OK] el contador crecio entre los dos GET")
            else:
                print("    [FALLO] el contador NO crecio")
        except RuntimeError as exc:
            print(f"    [ERROR] {exc}")


# --- IOPS y latencia en vivo (NIMBLE-MIB globalStats, PRESTADO) -----------
NIMBLE_UNITS = [
    {
        "agente": "hpe-storage-fc-01",
        "host": "127.0.0.30",
        "puerto": 16700,
        "usuario": "monitor_storagefc01",
        "auth_key": "RcVQ87sKGKNAXteaPhvF",
        "priv_key": "87KIBACIxZCukpKjai0Z",
    },
    {
        "agente": "hpe-storage-fc-02",
        "host": "127.0.0.31",
        "puerto": 16800,
        "usuario": "monitor_storagefc02",
        "auth_key": "SMkMLpmciBdaLR9pfDux",
        "priv_key": "2VcFacU3YHQ1CqwgAg7D",
    },
]
NIMBLE_OIDS = {
    "reads": "1.3.6.1.4.1.37447.1.3.2.0",
    "writes": "1.3.6.1.4.1.37447.1.3.4.0",
    "readtime": "1.3.6.1.4.1.37447.1.3.6.0",
    "writetime": "1.3.6.1.4.1.37447.1.3.7.0",
    "readbytes": "1.3.6.1.4.1.37447.1.3.8.0",
    "writebytes": "1.3.6.1.4.1.37447.1.3.10.0",
}


async def probar_iops_storage():
    print("\n=== IOPS y latencia calculados en vivo (NIMBLE-MIB, PRESTADO) ===")

    for cfg in NIMBLE_UNITS:
        print(f"\n  -- {cfg['agente']} --")
        try:
            t0 = time.time()
            v1 = {k: await _get_valor(cfg, oid) for k, oid in NIMBLE_OIDS.items()}
            time.sleep(5)
            t1 = time.time()
            v2 = {k: await _get_valor(cfg, oid) for k, oid in NIMBLE_OIDS.items()}
            dt = t1 - t0

            d_reads = v2["reads"] - v1["reads"]
            d_writes = v2["writes"] - v1["writes"]
            d_readtime = v2["readtime"] - v1["readtime"]
            d_writetime = v2["writetime"] - v1["writetime"]
            d_readbytes = v2["readbytes"] - v1["readbytes"]
            d_writebytes = v2["writebytes"] - v1["writebytes"]

            iops_r = d_reads / dt
            iops_w = d_writes / dt
            mbps_r = d_readbytes / dt / (1024 * 1024)
            mbps_w = d_writebytes / dt / (1024 * 1024)
            lat_r_ms = (d_readtime / d_reads) / 1000 if d_reads else 0
            lat_w_ms = (d_writetime / d_writes) / 1000 if d_writes else 0

            print(f"    intervalo medido = {dt:.2f} s")
            print(f"    IOPS lectura/escritura/total = {iops_r:.1f} / {iops_w:.1f} / {iops_r + iops_w:.1f}")
            print(f"    Throughput lectura/escritura = {mbps_r:.2f} / {mbps_w:.2f} MB/s")
            print(f"    Latencia media lectura/escritura = {lat_r_ms:.3f} / {lat_w_ms:.3f} ms")
            print("    [OK] los contadores crecieron" if d_reads > 0 and d_writes > 0
                  else "    [FALLO] los contadores no crecieron")
        except RuntimeError as exc:
            print(f"    [ERROR] {exc}")


# --- Walk completo del subarbol 1.3.6.1 vs. filas del public.snmprec -----
RAIZ_WALK = "1.3.6.1"


def _contar_filas_snmprec(nombre_agente):
    """Cuenta las filas OID|etiqueta|valor no comentadas/no vacias del
    public.snmprec del agente, y devuelve tambien la lista de sus OID
    (en el orden del archivo, que ya deberia ser ascendente)."""
    ruta = os.path.join(REPO_ROOT, "data", nombre_agente, "public.snmprec")
    oids = []
    with open(ruta, "r", encoding="ascii", errors="replace") as f:
        for raw_line in f:
            linea = raw_line.strip()
            if not linea or linea.startswith("#"):
                continue
            oid = linea.split("|", 1)[0]
            oids.append(oid)
    return oids


async def _walk_completo(agente):
    """Recorre por SNMPv3 (GETNEXT sucesivos) todo el subarbol RAIZ_WALK
    del agente y devuelve la lista de OID (numericos, como string) que
    respondio, en el orden en que los fue devolviendo."""
    snmpEngine = SnmpEngine()
    authData = UsmUserData(
        agente["usuario"],
        authKey=agente["auth_key"],
        privKey=agente["priv_key"],
        authProtocol=usmHMACSHAAuthProtocol,
        privProtocol=usmAesCfb128Protocol,
    )
    transportTarget = UdpTransportTarget(
        (agente["host"], agente["puerto"]), timeout=3, retries=1
    )
    contextData = ContextData(contextName="public")

    oids_devueltos = []
    current = ObjectIdentity(RAIZ_WALK)

    while True:
        errorIndication, errorStatus, errorIndex, varBinds = await nextCmd(
            snmpEngine,
            authData,
            transportTarget,
            contextData,
            ObjectType(current),
            lexicographicMode=False,
            lookupMib=False,
        )

        if errorIndication or errorStatus or not varBinds:
            break

        # nextCmd devuelve una fila (lista) de ObjectType por cada OID
        # solicitado; con un solo OID pedido, varBinds = [[ObjectType(...)]].
        # Con lookupMib=False, el nombre viene como ObjectName (no
        # ObjectIdentity), por eso se convierte con str() directo y se
        # reconstruye un ObjectIdentity nuevo para la siguiente consulta.
        nombre, _valor = varBinds[0][0]
        oid_str = str(nombre)

        if oid_str != RAIZ_WALK and not oid_str.startswith(RAIZ_WALK + "."):
            break  # se salio del subarbol pedido

        if oids_devueltos and oid_str == oids_devueltos[-1]:
            break  # proteccion contra bucles (fin de MIB: OID no avanza)

        oids_devueltos.append(oid_str)
        current = ObjectIdentity(oid_str)

    snmpEngine.closeDispatcher()
    return oids_devueltos


async def probar_walk_completo():
    print("\n=== Walk completo (GETNEXT sucesivos sobre 1.3.6.1) vs. public.snmprec ===")

    for agente in AGENTS:
        nombre = agente["nombre"]
        print(f"\n  -- {nombre} --")

        try:
            oids_archivo = _contar_filas_snmprec(nombre)
        except OSError as exc:
            print(f"    [ERROR] no se pudo leer public.snmprec: {exc}")
            continue

        oids_walk = await _walk_completo(agente)

        esperados = len(oids_archivo)
        obtenidos = len(oids_walk)
        print(f"    filas no comentadas en public.snmprec = {esperados}")
        print(f"    OID devueltos por el walk            = {obtenidos}")

        if obtenidos == esperados:
            print("    [OK] el walk devolvio la misma cantidad de OID que el archivo")
            continue

        faltan = esperados - obtenidos
        devueltos_set = set(oids_walk)
        primer_faltante = next(
            (oid for oid in oids_archivo if oid not in devueltos_set), None
        )
        print(f"    [FALLO] faltan {faltan} OID respecto del archivo")
        if primer_faltante:
            print(f"    Primer OID del archivo que el walk NO sirvio: {primer_faltante}")


async def main():
    for agente in AGENTS:
        await consultar_agente(agente)
    await probar_contadores_crecientes()
    await probar_iops_storage()
    await probar_walk_completo()


if __name__ == "__main__":
    asyncio.run(main())
