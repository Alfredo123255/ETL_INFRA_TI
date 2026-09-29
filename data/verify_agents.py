#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de verificacion de los agentes SNMPv3 simulados hpe-dl380-01,
hpe-dl360-01, hpe-c7000-01, hpe-bl460c-01 y hpe-bl460c-02.

Hace un GET contra sysDescr.0 y contra 2-4 OID mapeados (ver
mibs/hpe-real/MAPEO-SERVIDOR.md y mibs/hpe-real/MAPEO-CHASIS.md) de cada
agente, usando el patron UsmUserData/ContextData de pysnmp para
autenticacion SNMPv3 (auth=SHA, priv=AES). Al final, hace dos GET seguidos
(con una pausa corta entre medio) sobre un contador Counter32 (cpqnic, en
un servidor rack) y un contador Counter64 (ifHCInOctets, en el chasis) para
comprobar que los valores crecen (variacion `numeric` de snmpsim).

Uso: python data/verify_agents.py
"""
import asyncio
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
    usmAesCfb128Protocol,
    usmHMACSHAAuthProtocol,
)

# --- Credenciales y OID por agente (ver data/*/README.md) -------------
AGENTS = [
    {
        "nombre": "hpe-dl380-01",
        "host": "127.0.0.1",
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
        "host": "127.0.0.1",
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
        "host": "127.0.0.1",
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
        "host": "127.0.0.1",
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
        "host": "127.0.0.1",
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
]

# --- OID de contadores crecientes (variacion `numeric` de snmpsim) -----
CONTADOR_COUNTER32 = {
    "agente": "hpe-dl380-01",
    "host": "127.0.0.1",
    "puerto": 16100,
    "usuario": "monitor_dl380",
    "auth_key": "Kr7aY5nT2LdUco2B5IAZ",
    "priv_key": "GpoJkRAhPOZg3vA4qHyT",
    "etiqueta": "cpqNicIfPhysAdapterInOctets.2 (Counter32, tag 65)",
    "oid": "1.3.6.1.4.1.232.18.2.3.1.1.37.2",
}

CONTADOR_COUNTER64 = {
    "agente": "hpe-c7000-01",
    "host": "127.0.0.1",
    "puerto": 16300,
    "usuario": "monitor_c7000",
    "auth_key": "cy8EcO4BePPAN9Os5zts",
    "priv_key": "NR2yILtdOtWShA70stgf",
    "etiqueta": "ifHCInOctets puerto X1 (Counter64, tag 70)",
    "oid": "1.3.6.1.2.1.31.1.1.1.6.1",
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

    for cfg in (CONTADOR_COUNTER32, CONTADOR_COUNTER64):
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


async def main():
    for agente in AGENTS:
        await consultar_agente(agente)
    await probar_contadores_crecientes()


if __name__ == "__main__":
    asyncio.run(main())
