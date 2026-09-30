import asyncio
from dataclasses import replace
from ipaddress import ip_network
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
import api.main as main
from api.dto import separar_destino
from api.seguridad import resolver_destino
from etl.config import Configuracion, cargar_configuracion
from etl.detector import FABRICANTES, detectar_tipo, fabricante
from etl.snmp_cliente import mapear_error

CFG = Configuracion(SecretStr("api-test"))
BODY = dict(ip_gestion="127.0.0.1:16100", usuario="monitor", clave="secreto-auth", clave_privacidad="secreto-priv")
HEADERS = {"X-API-Key": "api-test"}
SUCCESS = dict(ok=True, descripcion="Equipo", sys_object_id="1.3.6.1.4.1.232.1",
               sys_name="equipo", fabricante="HPE", tipo_detectado="SERVIDOR", milisegundos=1)

@pytest.mark.parametrize("text,expected", [
    ("127.0.0.1", ("127.0.0.1", 161)), ("127.0.0.1:16100", ("127.0.0.1",16100)),
    ("switch.local:65535", ("switch.local",65535)), ("localhost",("localhost",161)),
    ("[::1]:16100",("::1",16100)), ("::1",("::1",161)),
])
def test_destinos(text, expected):
    assert separar_destino(text) == expected

@pytest.mark.parametrize("text", ["", " ", "256.2.3.4", "127.1", "host:0", "host:65536",
    "host:abc", "host:", "https://host", "host/path", "-host", "host..local",
    "host name", "[invalid]:161", "[::1]:", "127.0.0.1:1.5", "host:123456"])
def test_destino_invalido(text):
    with pytest.raises(ValueError):
        separar_destino(text)

@pytest.mark.parametrize("number,name", FABRICANTES.items())
def test_fabricantes(number, name):
    assert fabricante(f"1.3.6.1.4.1.{number}.1") == name

@pytest.mark.parametrize("oid", ["1.3.6.1.4.1.2320.1", "1.3.6.1.2.1.1", "malformado", "1.3.6.1.4.1"])
def test_fabricante_desconocido(oid):
    assert fabricante(oid) is None

@pytest.mark.parametrize("message,kind", [
    ("No SNMP response received before timeout","timeout"), ("Unknown USM user","usuario_desconocido"),
    ("Wrong SNMP PDU digest","clave_autenticacion"), ("Authenticator mismatched","clave_autenticacion"),
    ("Ciphering services not available or ciphertext is broken","clave_privacidad"),
    ("Unsupported SNMP security level","nivel_seguridad"), ("error no reconocido","otro")])
def test_mapeo_error(message, kind):
    assert mapear_error(message) == kind

@pytest.mark.parametrize("key,status", [(None,401),("incorrecta",401),("api-test",200)])
def test_api_key(monkeypatch, key, status):
    query = AsyncMock(return_value=SUCCESS.copy())
    monkeypatch.setattr(main,"probar_conexion",query)
    with TestClient(main.crear_app(CFG)) as client:
        response = client.post("/api/etl/probar-conexion", json=BODY,
                               headers={} if key is None else {"X-API-Key":key})
    assert response.status_code == status
    assert query.await_count == (1 if status == 200 else 0)

@pytest.mark.parametrize("changes", [
    {"clave":{"valor":"secreto-auth"}}, {"clave_privacidad":["secreto-priv"]},
    {"usuario":""}, {"ip_gestion":"host:0"}, {"clave":""}, {"clave_privacidad":" "},
    {"extra-secreto-auth":"secreto-priv"}])
def test_422_sin_secretos(changes, caplog):
    with TestClient(main.crear_app(CFG)) as client:
        response=client.post("/api/etl/probar-conexion",json=BODY|changes,headers=HEADERS)
    assert response.status_code == 422
    assert "secreto-auth" not in response.text + caplog.text
    assert "secreto-priv" not in response.text + caplog.text
    assert all(set(e)=={"campo","motivo"} for e in response.json()["detail"])

def test_json_invalido_sin_secretos():
    with TestClient(main.crear_app(CFG)) as client:
        response=client.post("/api/etl/probar-conexion",content='{"clave":"secreto-auth",',
                             headers=HEADERS|{"Content-Type":"application/json"})
    assert response.status_code==422 and "secreto-auth" not in response.text

def test_falla_200(monkeypatch):
    monkeypatch.setattr(main,"probar_conexion",AsyncMock(return_value=dict(
        ok=False,error_tipo="timeout",mensaje="Sin respuesta.",milisegundos=1)))
    with TestClient(main.crear_app(CFG)) as client:
        response=client.post("/api/etl/probar-conexion",json=BODY,headers=HEADERS)
    assert response.status_code==200 and response.json()["ok"] is False

def test_docs_y_cors():
    with TestClient(main.crear_app(CFG)) as client:
        assert client.get("/docs").status_code==404
        assert client.get("/openapi.json").status_code==404
        response=client.options("/api/etl/probar-conexion",headers={"Origin":"https://example.com"})
        assert "access-control-allow-origin" not in response.headers
    with TestClient(main.crear_app(replace(CFG,api_docs=True))) as client:
        assert client.get("/docs").status_code==200

def test_config_falla_cerrada(monkeypatch):
    monkeypatch.setattr("etl.config.load_dotenv", lambda *a: None)
    monkeypatch.delenv("ETL_API_KEY",raising=False)
    with pytest.raises(RuntimeError,match="ETL_API_KEY"):
        cargar_configuracion()

@pytest.mark.parametrize("var,value", [("SNMP_TIMEOUT","nan"),("SNMP_TIMEOUT","-1"),
    ("SNMP_RETRIES","-1"),("API_PORT","0"),("SNMP_REDES_PERMITIDAS","no-es-cidr")])
def test_config_invalida(monkeypatch,var,value):
    monkeypatch.setattr("etl.config.load_dotenv",lambda *a:None)
    monkeypatch.setenv(var,value)
    with pytest.raises(RuntimeError):
        cargar_configuracion()

async def test_prioridad_storage():
    query=AsyncMock(side_effect=[False,True])
    assert await detectar_tipo("1.3.6.1.4.1.232.9",query)=="STORAGE"
    assert [c.args[0] for c in query.call_args_list]==["1.3.6.1.4.1.232.22","1.3.6.1.4.1.232.16"]

async def test_prioridad_switch():
    query=AsyncMock(return_value=True)
    assert await detectar_tipo("1.3.6.1.4.1.47196.1",query)=="SWITCH"
    query.assert_awaited_once_with("1.3.6.1.4.1.47196")

async def test_deteccion_fallida():
    assert await detectar_tipo("1.3.6.1.4.1.232.1",AsyncMock(side_effect=OSError))=="DESCONOCIDO"

async def test_redes(monkeypatch):
    from fastapi import HTTPException
    networks=(ip_network("127.0.0.0/8"),)
    assert await resolver_destino("127.0.0.11",161,networks,1)=="127.0.0.11"
    with pytest.raises(HTTPException) as exc:
        await resolver_destino("10.0.0.1",161,networks,1)
    assert exc.value.status_code==422
    # DNS con respuestas mixtas debe rechazarse, no escoger solo la permitida.
    monkeypatch.setattr(asyncio.get_running_loop(),"getaddrinfo",AsyncMock(return_value=[
        (2,2,17,"",("127.0.0.1",161)),(2,2,17,"",("10.0.0.1",161))]))
    with pytest.raises(HTTPException):
        await resolver_destino("switch.local",161,networks,1)

async def test_semaforo(monkeypatch):
    import httpx
    active=peak=0
    async def query(*args):
        nonlocal active,peak
        active+=1
        peak=max(peak,active)
        await asyncio.sleep(.03)
        active-=1
        return SUCCESS.copy()
    monkeypatch.setattr(main,"probar_conexion",query)
    app=main.crear_app(CFG)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            results=await asyncio.gather(*[client.post("/api/etl/probar-conexion",json=BODY,headers=HEADERS) for _ in range(12)])
    assert all(r.status_code==200 for r in results)
    assert peak==5
