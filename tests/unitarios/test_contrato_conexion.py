"""Regresión del contrato: una credencial y una fecha en el activo, sin BD real."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from pydantic import SecretStr
import pytest
from etl.config import Configuracion
from etl import monitoreo, programador
from etl.snmp_cliente import ConexionSNMP, SesionSNMP


def base_simulada(monkeypatch):
    db = MagicMock()
    cur = db.cursor.return_value.__enter__.return_value
    contexto = MagicMock()
    contexto.return_value.__enter__.return_value = db
    monkeypatch.setattr(monitoreo, "conexion_bd", contexto)
    return db, cur, contexto


def test_programador_usa_fecha_activo_y_solo_conexiones_habilitadas(monkeypatch):
    _, cur, contexto = base_simulada(monkeypatch)
    monkeypatch.setattr(programador, "conexion_bd", contexto)
    programador.conexiones_programadas(None)
    sql = cur.execute.call_args.args[0]
    assert "a.ultima_actualizacion" in sql
    assert "fecha_ultima_actualizacion" not in sql
    assert "('Activo', 'Sin conexión')" in sql
    assert "<> 'Baja'" in sql


@pytest.mark.parametrize("estado,eventos", [("Activo", 1), ("Sin conexión", 0)])
def test_fallo_no_escribe_fecha_y_no_duplica_eventos(monkeypatch, estado, eventos):
    _, cur, _ = base_simulada(monkeypatch)
    ref = monitoreo.ConexionMonitoreo(1, 2, "127.0.0.1", "HPE", SecretStr("Enterprise"))
    monkeypatch.setattr(monitoreo, "_bloquear_conexion", lambda *a: {"estado_conexion": estado})
    cur.fetchone.return_value = {"estado_operativo": "Encendido"}
    evento = MagicMock()
    monkeypatch.setattr(monitoreo, "registrar_evento_estado", evento)
    resultado = monitoreo.registrar_fallo(None, ref, "timeout")
    assert resultado["eventos"] == eventos
    assert evento.call_count == eventos
    assert all("actualizacion" not in c.args[0] for c in cur.execute.call_args_list)


def test_exito_sin_cambios_actualiza_fecha_y_guarda_metricas(monkeypatch):
    _, cur, _ = base_simulada(monkeypatch)
    ref = monitoreo.ConexionMonitoreo(1, 2, "127.0.0.1", "HPE", SecretStr("Enterprise"))
    anterior = {"id": 2, "numero_serie": "SERIE", "tipo_activo": "SWITCH",
                "estado_operativo": "Encendido", "ultima_actualizacion": datetime(2025, 1, 1)}
    cur.fetchone.side_effect = [anterior, {}]
    monkeypatch.setattr(monitoreo, "_bloquear_conexion", lambda *a: {"estado_conexion": "Activo"})
    metricas = MagicMock()
    monkeypatch.setattr(monitoreo, "guardar_metricas", metricas)
    ficha = {"activo": dict(anterior), "switch": {}, "componentes": {},
             "mediciones": [{"nombre_metrica": "temperatura", "valor": 25}]}
    resultado = monitoreo.guardar_iteracion(Configuracion(SecretStr("test")), ref, ficha)
    assert resultado["ok"] and resultado["eventos"] == 0
    metricas.assert_called_once()
    escrituras = [c for c in cur.execute.call_args_list if c.args[0].startswith("UPDATE activo")]
    assert len(escrituras) == 1 and "ultima_actualizacion=%s" in escrituras[0].args[0]
    assert escrituras[0].args[1][0] > anterior["ultima_actualizacion"]
    assert all("fecha_ultima_actualizacion" not in c.args[0] for c in cur.execute.call_args_list)


def test_fallo_espera_frecuencia_sin_alterar_fecha_persistida():
    ahora = datetime(2026, 10, 25, 12)
    ultima = ahora - timedelta(hours=1)
    filas = [(1, 300, ultima)]
    assert programador.conexiones_vencidas(filas, {1: ahora}, ahora) == []
    assert programador.conexiones_vencidas(filas, {1: ahora}, ahora + timedelta(seconds=300)) == [1]


def test_sesion_usa_misma_clave_para_auth_y_privacidad(monkeypatch):
    import etl.snmp_cliente as snmp
    auth = MagicMock()
    monkeypatch.setattr(snmp, "UsmUserData", auth)
    monkeypatch.setattr(snmp, "SnmpEngine", MagicMock())
    monkeypatch.setattr(snmp, "UdpTransportTarget", MagicMock())
    conexion = ConexionSNMP("127.0.0.1", 161, "HPE", SecretStr("Enterprise"))
    with SesionSNMP(conexion):
        assert auth.call_args.kwargs["authKey"] == auth.call_args.kwargs["privKey"] == "Enterprise"
