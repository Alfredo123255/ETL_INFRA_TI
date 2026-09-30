from dataclasses import replace
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest
import psycopg2
from fastapi.testclient import TestClient
from pydantic import SecretStr

import api.main as api
import etl.db as db
import etl.carga as carga
from etl.config import Configuracion
from etl.errores import ActivoDuplicado, BaseNoDisponible, DatosIncompletos, ErrorExtraccion
from etl.normalizacion.servidor import normalizar_servidor_hpe
from tests.unitarios.test_servidor import FECHA, registros

CFG = Configuracion(SecretStr("api-test"), database_url=SecretStr("postgresql://test:test@localhost/inventario"))
HEADERS = {"X-API-Key": "api-test"}
BODY = {"ip_gestion": "127.0.0.1:16100", "usuario": "monitor",
        "clave": "secreto-auth", "clave_privacidad": "secreto-priv"}
PATH = "/api/etl/crear-activo"


@pytest.fixture
def ficha():
    resultado = normalizar_servidor_hpe(registros("hpe-dl380-01"), fecha_actualizacion=FECHA)
    resultado["activo"]["ip_gestion"] = BODY["ip_gestion"]
    return resultado


@pytest.fixture
def conexion(monkeypatch):
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    numero_id = 9

    def ejecutar(sql, parametros):
        nonlocal numero_id
        if sql.startswith("SELECT"):
            cursor.fetchone.return_value = ("DataCenter-1",)
        elif "RETURNING id" in sql:
            numero_id += 1
            cursor.fetchone.return_value = (numero_id,)
    cursor.execute.side_effect = ejecutar
    monkeypatch.setattr(db, "obtener_conexion", lambda config: connection)
    return connection, cursor


def test_registro_guarda_relaciones_modelo_y_metricas(ficha, conexion):
    connection, cursor = conexion
    resultado = carga.cargar_registro(CFG, ficha)
    assert resultado["activo_id"] == 10
    assert resultado["ubicacion"] == "DataCenter-1"
    assert resultado["componentes"]["cpu"] == 2
    assert resultado["componentes"]["puerto_tarjeta_red"] == 2
    assert resultado["metricas_guardadas"] == 4
    llamadas = [(c.args[0], c.args[1]) for c in cursor.execute.call_args_list]
    assert llamadas[0][1] == ("DataCenter-1",)
    assert "ON CONFLICT (nombre_modelo) DO NOTHING" in llamadas[1][0]
    for sql, valores in llamadas:
        if sql.startswith("INSERT INTO servidor"):
            assert valores[0] == 10
        if sql.startswith("INSERT INTO cpu"):
            assert valores[0] == 10
    puertos = [valores for sql, valores in llamadas if sql.startswith("INSERT INTO puerto_tarjeta_red")]
    tarjetas = [c for c in cursor.execute.call_args_list if c.args[0].startswith("INSERT INTO tarjeta_red ")]
    assert len(puertos) == len(tarjetas) == 2
    assert puertos[0][0] != puertos[1][0]
    sql_metricas, metricas = cursor.executemany.call_args.args
    assert "metrica_historica" in sql_metricas
    assert all(m[0] == 10 and m[5].tzinfo is None for m in metricas)
    valores_metricas = {m[3]: m[4] for m in metricas}
    assert valores_metricas["cpu_uso_ghz"] == Decimal("35.28")
    assert valores_metricas["ram_uso_gb"] == 74
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once()


def test_datacenter_ausente_deshace_registro(ficha, conexion):
    connection, cursor = conexion
    cursor.execute.side_effect = lambda *args: None
    cursor.fetchone.return_value = None
    with pytest.raises(DatosIncompletos):
        carga.cargar_registro(CFG, ficha)
    assert cursor.execute.call_count == 1
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_fallo_al_guardar_metricas_deshace_todos_los_componentes(ficha, conexion):
    connection, cursor = conexion
    cursor.executemany.side_effect = psycopg2.OperationalError("detalle interno")
    with pytest.raises(BaseNoDisponible, match="registro en PostgreSQL"):
        carga.cargar_registro(CFG, ficha)
    assert any("INSERT INTO disco" in c.args[0] for c in cursor.execute.call_args_list)
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    connection.close.assert_called_once()


def test_serie_duplicada_no_se_actualiza(ficha, conexion):
    class Duplicado(psycopg2.IntegrityError):
        pgcode = "23505"
    connection, cursor = conexion
    original = cursor.execute.side_effect
    def ejecutar(sql, valores):
        if sql.startswith("INSERT INTO activo "):
            raise Duplicado("serie secreta")
        original(sql, valores)
    cursor.execute.side_effect = ejecutar
    with pytest.raises(ActivoDuplicado) as exc:
        carga.cargar_registro(CFG, ficha)
    assert "serie secreta" not in str(exc.value)
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_texto_del_modelo_se_envia_como_parametro(ficha, conexion):
    texto = "modelo'); DROP TABLE activo; --"
    ficha["activo"]["modelo"] = texto
    carga.cargar_registro(CFG, ficha, ubicacion="DataCenter-1")
    for llamada in conexion[1].execute.call_args_list:
        assert texto not in llamada.args[0]
    assert conexion[1].execute.call_args_list[1].args[1] == (texto,)


def test_ubicacion_explicitamente_enviada_tiene_prioridad(ficha, conexion):
    carga.cargar_registro(CFG, ficha, ubicacion="Datacenter real")
    assert conexion[1].execute.call_args_list[0].args[1] == ("Datacenter real",)


def test_conexion_no_expone_password(monkeypatch):
    monkeypatch.setattr(db.psycopg2, "connect", MagicMock(side_effect=psycopg2.OperationalError("password secreta")))
    with pytest.raises(BaseNoDisponible) as exc:
        db.obtener_conexion(CFG)
    assert "secreta" not in str(exc.value)


@pytest.fixture
def preparar_api(monkeypatch, ficha):
    query = AsyncMock(return_value=ficha)
    monkeypatch.setattr(api, "preparar_registro_servidor", query)
    resultado = {"ok": True, "activo_id": 10, "numero_serie": "CZ38010ABC",
        "hostname": "hpe-dl380-01", "fabricante": "HPE", "tipo_activo": "SERVIDOR",
        "modelo": "ProLiant DL380 Gen10", "ubicacion": "DataCenter-1",
        "componentes": {"cpu": 2}, "metricas_guardadas": 4}
    guardar = MagicMock(return_value=resultado)
    monkeypatch.setattr(api, "cargar_registro", guardar)
    return query, guardar


def test_api_crea_y_reutiliza_etl(preparar_api):
    query, guardar = preparar_api
    with TestClient(api.crear_app(CFG)) as client:
        respuesta = client.post(PATH, json=BODY, headers=HEADERS)
    assert respuesta.status_code == 201
    assert respuesta.json()["activo_id"] == 10
    query.assert_awaited_once()
    guardar.assert_called_once()
    conexion = query.call_args.args[0]
    assert conexion.host == "127.0.0.1" and conexion.puerto == 16100
    assert "secreto-auth" not in respuesta.text and "secreto-priv" not in respuesta.text


@pytest.mark.parametrize("cambios", [{"tipo_servidor": "INVALIDO"}, {"ubicacion": " "}, {"clave": ""}])
def test_validacion_sin_extraccion(preparar_api, cambios):
    with TestClient(api.crear_app(CFG)) as client:
        respuesta = client.post(PATH, json=BODY | cambios, headers=HEADERS)
    assert respuesta.status_code == 422
    assert "secreto-auth" not in respuesta.text
    preparar_api[0].assert_not_awaited()


def test_registro_requiere_api_key(preparar_api):
    with TestClient(api.crear_app(CFG)) as client:
        respuesta = client.post(PATH, json=BODY)
    assert respuesta.status_code == 401
    preparar_api[0].assert_not_awaited()


def test_sin_base_no_consulta_snmp(preparar_api):
    with TestClient(api.crear_app(replace(CFG, database_url=None))) as client:
        respuesta = client.post(PATH, json=BODY, headers=HEADERS)
    assert respuesta.status_code == 503
    preparar_api[0].assert_not_awaited()


@pytest.mark.parametrize("error,status", [(ErrorExtraccion("timeout"), 504),
    (ErrorExtraccion("clave_autenticacion"), 502), (DatosIncompletos("Datos insuficientes."), 422)])
def test_fallo_snmp_no_guarda(preparar_api, error, status):
    preparar_api[0].side_effect = error
    with TestClient(api.crear_app(CFG)) as client:
        respuesta = client.post(PATH, json=BODY, headers=HEADERS)
    assert respuesta.status_code == status
    preparar_api[1].assert_not_called()


@pytest.mark.parametrize("error,status", [(ActivoDuplicado("Activo existente."), 409),
    (BaseNoDisponible("Base no disponible."), 503), (DatosIncompletos("Datacenter inexistente."), 422)])
def test_api_fallos_persistencia(preparar_api, error, status):
    preparar_api[1].side_effect = error
    with TestClient(api.crear_app(CFG)) as client:
        respuesta = client.post(PATH, json=BODY, headers=HEADERS)
    assert respuesta.status_code == status
