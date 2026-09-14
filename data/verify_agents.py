#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de verificacion de los agentes SNMPv3 simulados hpe-dl380-01,
hpe-dl360-01 y hpe-c7000-01.

Hace un GET contra sysDescr.0 y contra 2-3 OID mapeados (ver
mibs/hpe-real/MAPEO-SERVIDOR.md y mibs/hpe-real/MAPEO-CHASIS.md) de cada
agente, usando el patron UsmUserData/ContextData de pysnmp para
autenticacion SNMPv3 (auth=SHA, priv=AES).

Uso: python data/verify_agents.py
"""
import asyncio

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
        ],
    },
]


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


async def main():
    for agente in AGENTS:
        await consultar_agente(agente)


if __name__ == "__main__":
    asyncio.run(main())
