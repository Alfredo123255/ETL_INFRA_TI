"""Pruebas reales de API; solo se omiten agentes que no responden."""
from dataclasses import replace
import socket
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from api.main import crear_app
from etl.config import Configuracion
from tests.integracion.agentes import EXPECTED,leer_agente

pytestmark=pytest.mark.integracion
CFG=Configuracion(SecretStr("api-integracion"),snmp_context_name="public")
HEADERS={"X-API-Key":"api-integracion"}
PATH="/api/etl/probar-conexion"

@pytest.mark.parametrize("name,kind",EXPECTED.items(),ids=EXPECTED.keys())
def test_agente(name,kind):
    body=leer_agente(name)
    with TestClient(crear_app(CFG)) as client:
        response=client.post(PATH,json=body,headers=HEADERS)
    assert response.status_code==200
    result=response.json()
    if result.get("error_tipo")=="timeout":
        pytest.skip("El agente no responde: "+name)
    assert result["ok"], result
    assert result["tipo_detectado"]==kind
    expected_vendor="HPE Aruba Networking" if kind=="SWITCH" else "HPE"
    assert result["fabricante"]==expected_vendor
    print(f"\n{name} | {result['ok']} | {result['fabricante']} | {result['tipo_detectado']} | {result['milisegundos']} ms")

@pytest.mark.parametrize("case,expected", [
    ("puerto_sin_agente","timeout"),("usuario","usuario_desconocido"),
    ("autenticacion","clave_autenticacion"),("privacidad","clave_privacidad")])
def test_errores(case,expected):
    body=leer_agente("hpe-dl380-01")
    with TestClient(crear_app(CFG)) as client:
        baseline=client.post(PATH,json=body,headers=HEADERS).json()
        if baseline.get("error_tipo")=="timeout":
            pytest.skip("Agente de referencia no disponible")
        assert baseline["ok"],baseline
        sock=None
        try:
            if case=="puerto_sin_agente":
                sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                sock.bind(("127.0.0.1",0))
                body["ip_gestion"]=f"127.0.0.1:{sock.getsockname()[1]}"
            elif case=="usuario":
                body["usuario"]="usuario_inexistente_test"
            elif case=="autenticacion":
                body["clave"]="auth-incorrecta-test"
            else:
                body["clave_privacidad"]="priv-incorrecta-test"
            response=client.post(PATH,json=body,headers=HEADERS)
        finally:
            if sock:
                sock.close()
    assert response.status_code==200
    result=response.json()
    assert result["ok"] is False
    assert result["error_tipo"]==expected,result
    for field in ("usuario","clave","clave_privacidad"):
        assert body[field] not in response.text
    print(f"\n{case} | {result['error_tipo']} | {result['milisegundos']} ms")
