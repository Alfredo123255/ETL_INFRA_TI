"""Comprueba la transición por fallo SNMP sin necesitar un agente en ejecución."""
import os
import asyncio
from datetime import date, datetime
from urllib.parse import urlparse
from uuid import uuid4

import psycopg2
import pytest
from pydantic import SecretStr

from etl.config import Configuracion
from etl.monitoreo import ConexionMonitoreo, ejecutar_iteracion, guardar_iteracion, leer_conexion, registrar_fallo
from etl.programador import conexiones_programadas

pytestmark = pytest.mark.integracion


def test_fallo_no_mueve_fechas_y_registra_una_sola_transicion():
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("Falta TEST_DATABASE_URL")
    if "test" not in urlparse(url).path.lower() or url == os.environ.get("DATABASE_URL", "").strip():
        pytest.fail("TEST_DATABASE_URL debe apuntar exclusivamente a una base de prueba")
    marca = "ETL-FALLO-" + uuid4().hex[:12]
    fecha_activo = date(2025, 1, 2)
    fecha_conexion = datetime(2025, 1, 2, 3, 4, 5)
    activo_id = conexion_id = None
    try:
        with psycopg2.connect(url) as db, db.cursor() as cur:
            cur.execute("INSERT INTO datacenters(nombre) VALUES (%s)", (marca,))
            cur.execute("""INSERT INTO activo(numero_serie,hostname,ubicacion,tipo_activo,
                estado_operativo,ultima_actualizacion) VALUES (%s,%s,%s,'SWITCH','Encendido',%s)
                RETURNING id""", (marca, marca, marca, fecha_activo))
            activo_id = cur.fetchone()[0]
            cur.execute("""INSERT INTO monitoreo_snmp(ip_gestion,usuario,clave,
                frecuencia_actualizacion,estado_conexion,fecha_ultima_actualizacion,activo_id)
                VALUES ('127.0.0.1:1','test','test',60,'Activo',%s,%s) RETURNING id""",
                (fecha_conexion, activo_id))
            conexion_id = cur.fetchone()[0]
        referencia = ConexionMonitoreo(conexion_id, activo_id, "127.0.0.1:1",
                                       "test", SecretStr("test"), None)
        config = Configuracion(SecretStr("test"), database_url=SecretStr(url))
        assert registrar_fallo(config, referencia, "timeout")["eventos"] == 1
        assert registrar_fallo(config, referencia, "timeout")["eventos"] == 0
        with psycopg2.connect(url) as db, db.cursor() as cur:
            cur.execute("SELECT ultima_actualizacion FROM activo WHERE id=%s", (activo_id,))
            assert cur.fetchone()[0] == fecha_activo
            cur.execute("""SELECT estado_conexion,fecha_ultima_actualizacion
                FROM monitoreo_snmp WHERE id=%s""", (conexion_id,))
            assert cur.fetchone() == ("Sin conexión", fecha_conexion)
            cur.execute("""SELECT campo,valor_nuevo,count(*) FROM historico_estado
                WHERE activo_id=%s GROUP BY campo,valor_nuevo""", (activo_id,))
            assert cur.fetchall() == [("estado_conexion", "Sin conexión", 1)]
            cur.execute("UPDATE monitoreo_snmp SET estado_conexion='Inactivo' WHERE id=%s", (conexion_id,))
        assert leer_conexion(config, conexion_id) is None
        assert conexiones_programadas(config, conexion_id) == []
        assert asyncio.run(ejecutar_iteracion(config, conexion_id)) == {"conexion_id": conexion_id, "omitida": True}
        assert guardar_iteracion(config, referencia, {"activo": {"tipo_activo": "SWITCH"},
                                                   "switch": {}, "mediciones": []}) == {
                                                       "conexion_id": conexion_id, "omitida": True}
        assert registrar_fallo(config, referencia, "timeout")["eventos"] == 0
        with psycopg2.connect(url) as db, db.cursor() as cur:
            cur.execute("SELECT estado_conexion,fecha_ultima_actualizacion FROM monitoreo_snmp WHERE id=%s", (conexion_id,))
            assert cur.fetchone() == ("Inactivo", fecha_conexion)
    finally:
        if activo_id is not None:
            with psycopg2.connect(url) as db, db.cursor() as cur:
                cur.execute("DELETE FROM historico_estado WHERE activo_id=%s", (activo_id,))
                if conexion_id is not None:
                    cur.execute("DELETE FROM monitoreo_snmp WHERE id=%s", (conexion_id,))
                cur.execute("DELETE FROM activo WHERE id=%s", (activo_id,))
                cur.execute("DELETE FROM datacenters WHERE nombre=%s", (marca,))
