"""Extracción real contra los agentes SNMP locales de servidor."""
from datetime import date
from pathlib import Path
import asyncio
import socket
import subprocess
import sys
from time import monotonic
import pytest
from pydantic import SecretStr
from api.dto import separar_destino
from etl.extraccion.servidor import extraer_servidor_hpe
from etl.normalizacion.servidor import normalizar_servidor_hpe
from etl.snmp_cliente import ConexionSNMP, probar_conexion
from etl.config import Configuracion
from tests.integracion.agentes import leer_agente

pytestmark = pytest.mark.integracion


@pytest.mark.parametrize("agente", ["hpe-dl380-01", "hpe-dl360-01"])
async def test_extraccion_servidor_local(agente, tmp_path):
    pytest.importorskip("snmpsim")
    config = leer_agente(agente)
    host, puerto = separar_destino(config["ip_gestion"])
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservado:
        reservado.bind(("127.0.0.1", 0))
        puerto = reservado.getsockname()[1]
    host = "127.0.0.1"
    conexion = ConexionSNMP(host, puerto, config["usuario"], SecretStr(config["clave"]),
                            SecretStr(config["clave_privacidad"]), contexto="public", timeout=.5, reintentos=0)
    raiz = Path(__file__).resolve().parents[2]
    comando = [sys.executable, str(raiz / "data" / "run_responder.py"),
        "--v3-engine-id=8000000001abcdef12", "--v3-user=" + config["usuario"],
        "--v3-auth-key=" + config["clave"], "--v3-auth-proto=SHA",
        "--v3-priv-key=" + config["clave_privacidad"], "--v3-priv-proto=AES",
        f"--agent-udpv4-endpoint={host}:{puerto}", "--data-dir=" + str(raiz / "data" / agente),
        "--cache-dir=" + str(tmp_path)]
    cfg = Configuracion(SecretStr("test"), snmp_context_name="public", snmp_timeout=.5, snmp_retries=0)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proceso = subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    try:
        plazo = monotonic() + 15
        while True:
            assert proceso.poll() is None, "El simulador terminó antes de estar disponible."
            prueba = await probar_conexion(host, puerto, conexion.usuario, conexion.clave, conexion.clave_privacidad, cfg)
            if prueba["ok"]:
                break
            assert prueba["error_tipo"] == "timeout", prueba
            assert monotonic() < plazo, "El simulador no quedó disponible."
            await asyncio.sleep(.1)
        datos = await extraer_servidor_hpe(conexion)
    finally:
        proceso.terminate()
        proceso.wait(timeout=10)
    ficha = normalizar_servidor_hpe(datos, fecha_actualizacion=date(2026, 9, 30))
    assert ficha["activo"]["hostname"] == agente
    assert ficha["componentes"]["cpu"]
    assert ficha["componentes"]["disco"][0]["numero_serial"]
    assert ficha["componentes"]["ram"][0]["numero_serial"]
