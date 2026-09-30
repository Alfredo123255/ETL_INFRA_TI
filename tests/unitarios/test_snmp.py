import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import SecretStr
from pysnmp.proto import rfc1902,rfc1905
import etl.snmp_cliente as snmp
from etl.config import Configuracion

CFG=Configuracion(SecretStr("api"))
BINDINGS=[(rfc1902.ObjectName(o),v) for o,v in zip(snmp.SYSTEM_OIDS,[
    rfc1902.OctetString("Equipo"),rfc1902.ObjectIdentifier("1.3.6.1.4.1.232.9"),
    rfc1902.OctetString("nombre")])]

@pytest.fixture
def motor(monkeypatch):
    engine=MagicMock()
    monkeypatch.setattr(snmp,"SnmpEngine",lambda:engine)
    monkeypatch.setattr(snmp,"UdpTransportTarget",MagicMock())
    return engine

async def consultar():
    return await snmp.probar_conexion("127.0.0.1",161,"monitor",SecretStr("auth-secreta"),None,CFG)

async def test_deteccion_no_invalida_conexion(monkeypatch,motor):
    monkeypatch.setattr(snmp,"getCmd",AsyncMock(return_value=(None,0,0,BINDINGS)))
    monkeypatch.setattr(snmp,"nextCmd",AsyncMock(side_effect=OSError("secreto")))
    result=await consultar()
    assert result["ok"] and result["tipo_detectado"]=="DESCONOCIDO"
    motor.closeDispatcher.assert_called_once()

async def test_getnext_fuera_subarbol(monkeypatch,motor):
    monkeypatch.setattr(snmp,"getCmd",AsyncMock(return_value=(None,0,0,BINDINGS)))
    monkeypatch.setattr(snmp,"nextCmd",AsyncMock(return_value=(None,0,0,[[
        (rfc1902.ObjectName("1.3.6.1.4.1.232.220.1"),rfc1902.Integer(1))]])))
    assert (await consultar())["tipo_detectado"]=="DESCONOCIDO"

async def test_fin_mib(monkeypatch,motor):
    monkeypatch.setattr(snmp,"getCmd",AsyncMock(return_value=(None,0,0,BINDINGS)))
    monkeypatch.setattr(snmp,"nextCmd",AsyncMock(return_value=(None,0,0,[[
        (rfc1902.ObjectName("1.3.6.1.4.1.232.22.1"),rfc1905.EndOfMibView())]])))
    assert (await consultar())["tipo_detectado"]=="DESCONOCIDO"

async def test_excepcion_no_expone_secretos(monkeypatch,motor):
    monkeypatch.setattr(snmp,"getCmd",AsyncMock(side_effect=RuntimeError("auth-secreta monitor")))
    result=await consultar()
    assert not result["ok"] and "auth-secreta" not in str(result) and "monitor" not in str(result)
    motor.closeDispatcher.assert_called_once()

async def test_cancelacion_cierra_motor(monkeypatch,motor):
    monkeypatch.setattr(snmp,"getCmd",AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await consultar()
    motor.closeDispatcher.assert_called_once()

async def test_privacidad_reutiliza_autenticacion(monkeypatch,motor):
    auth=MagicMock()
    monkeypatch.setattr(snmp,"UsmUserData",auth)
    monkeypatch.setattr(snmp,"getCmd",AsyncMock(return_value=("timeout",0,0,[])))
    await consultar()
    assert auth.call_args.kwargs["authKey"]==auth.call_args.kwargs["privKey"]=="auth-secreta"
