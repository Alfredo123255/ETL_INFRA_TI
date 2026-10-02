"""Altas reales contra una base PostgreSQL de PRUEBA y agentes SNMP simulados.

Requiere TEST_DATABASE_URL (base con el esquema ya aplicado y nombre que contenga "test") y los
agentes de data/ en marcha. Se omite si falta cualquiera. Nunca usa DATABASE_URL.
Al iniciar vacía las tablas de la base de prueba y vuelve a sembrar datacenter, clúster y conexiones.
"""
import os
from urllib.parse import urlparse
import psycopg2
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from api.main import crear_app
from etl.config import Configuracion
from tests.integracion.agentes import EXPECTED, leer_agente

pytestmark = pytest.mark.integracion
URL = os.environ.get("TEST_DATABASE_URL", "").strip()
HEADERS = {"X-API-Key": "api-integracion"}
PATH = "/api/etl/crear-activo"
DATACENTER, CLUSTER = "DC-LAB-LOCAL", "CLUSTER-LAB-LOCAL"
# El chasis primero, para que los blades se enlacen a sus slots.
ORDEN = ["hpe-c7000-01", "hpe-dl380-01", "hpe-dl360-01", "hpe-bl460c-01", "hpe-bl460c-02",
         "hpe-storage-fc-01", "hpe-storage-fc-02", "aruba-cx-sw01"]
TABLAS = ("historico_estado, metrica_historica, monitoreo_snmp, activo, clusters, datacenters, modelos")


def _conectar():
    return psycopg2.connect(URL, connect_timeout=5)


@pytest.fixture(scope="module")
def base():
    if not URL:
        pytest.skip("TEST_DATABASE_URL no está definida")
    nombre = urlparse(URL).path.lstrip("/")
    if "test" not in nombre.lower() or URL == os.environ.get("DATABASE_URL", "").strip():
        pytest.fail("TEST_DATABASE_URL debe apuntar a una base de prueba (nombre con 'test'), no a la real")
    conexiones = {}
    with _conectar() as c, c.cursor() as cur:
        cur.execute(f"TRUNCATE {TABLAS} RESTART IDENTITY CASCADE")
        cur.execute("INSERT INTO datacenters (nombre) VALUES (%s)", (DATACENTER,))
        cur.execute("INSERT INTO clusters (nombre, ambiente, datacenter) VALUES (%s,'DESARROLLO',%s)",
                    (CLUSTER, DATACENTER))
        for nombre_agente in ORDEN:
            a = leer_agente(nombre_agente)
            cur.execute("""INSERT INTO monitoreo_snmp (ip_gestion, usuario, clave, clave_privacidad,
                frecuencia_actualizacion, estado_conexion) VALUES (%s,%s,%s,%s,60,'Inactivo') RETURNING id""",
                (a["ip_gestion"], a["usuario"], a["clave"], a["clave_privacidad"]))
            conexiones[nombre_agente] = cur.fetchone()[0]
    return conexiones


@pytest.fixture(scope="module")
def cliente(base):
    config = Configuracion(SecretStr("api-integracion"), snmp_context_name="public",
                           database_url=SecretStr(URL))
    with TestClient(crear_app(config)) as client:
        yield client


@pytest.fixture(scope="module")
def altas(base, cliente):
    respuestas = {}
    for nombre in ORDEN:
        r = cliente.post(PATH, json={"conexion_id": base[nombre], "cluster_id": CLUSTER}, headers=HEADERS)
        if r.status_code in (502, 504):
            pytest.skip(f"El agente no responde: {nombre}")
        assert r.status_code == 201, (nombre, r.status_code, r.text)
        respuestas[nombre] = r.json()
    return respuestas


def _eventos():
    with _conectar() as c, c.cursor() as cur:
        cur.execute("""SELECT h.activo_id, a.hostname, h.campo, h.valor_nuevo, h.componente_tipo,
            h.componente_sn, h.descripcion, h.fecha_cambio FROM historico_estado h
            JOIN activo a ON a.id=h.activo_id ORDER BY h.id""")
        return cur.fetchall()


@pytest.mark.parametrize("nombre", ORDEN)
def test_dos_eventos_por_activo(altas, nombre):
    tipo = EXPECTED[nombre]
    assert altas[nombre]["tipo_activo"] == tipo
    assert altas[nombre]["eventos_registrados"] == 2
    filas = [f for f in _eventos() if f[0] == altas[nombre]["activo_id"]]
    assert [(f[2], f[3], f[4], f[5]) for f in filas] == [
        ("estado_operativo", altas[nombre]["estado_operativo"], None, None),
        ("estado_conexion", "Activo", None, None)]
    assert [f[6] for f in filas] == ["Estado inicial al registrar el activo",
                                     "Conexión SNMP vinculada al registrar el activo"]
    assert filas[0][7] == filas[1][7]


def test_fecha_coincide_con_las_metricas(altas):
    with _conectar() as c, c.cursor() as cur:
        cur.execute("""SELECT count(*) FROM historico_estado h WHERE NOT EXISTS (
            SELECT 1 FROM metrica_historica m WHERE m.activo_id=h.activo_id AND m.fecha_medicion=h.fecha_cambio)""")
        assert cur.fetchone()[0] == 0


def test_storage_con_disco_degradado_nace_degradado(altas):
    assert altas["hpe-storage-fc-01"]["estado_operativo"] == "Degradado"
    fila = next(f for f in _eventos() if f[1] == "hpe-storage-fc-01" and f[2] == "estado_operativo")
    assert fila[3] == "Degradado"


def test_estado_del_evento_coincide_con_el_activo(altas):
    with _conectar() as c, c.cursor() as cur:
        cur.execute("""SELECT count(*) FROM historico_estado h JOIN activo a ON a.id=h.activo_id
            WHERE h.campo='estado_operativo' AND h.valor_nuevo<>a.estado_operativo""")
        assert cur.fetchone()[0] == 0


def test_segundo_alta_409_no_agrega_eventos(altas, base, cliente):
    antes = len(_eventos())
    r = cliente.post(PATH, json={"conexion_id": base["hpe-dl380-01"], "cluster_id": CLUSTER}, headers=HEADERS)
    assert r.status_code == 409
    assert len(_eventos()) == antes == 2 * len(ORDEN)


def test_imprime_historico_completo(altas, capsys):
    with capsys.disabled():
        print("\nactivo_id | campo | valor_nuevo | componente_tipo | descripcion | fecha_cambio")
        for f in _eventos():
            print(f[0], f[2], f[3], f[4], f[6], f[7], sep=" | ")
