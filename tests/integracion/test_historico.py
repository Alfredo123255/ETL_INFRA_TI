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


@pytest.mark.parametrize("nombre", ORDEN)
def test_iteracion_periodica_guarda_metricas_y_conserva_eventos(altas, base, cliente, nombre):
    import asyncio
    from etl.monitoreo import ejecutar_iteracion
    activo_id = altas[nombre]["activo_id"]
    with _conectar() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM metrica_historica WHERE activo_id=%s", (activo_id,))
        metricas_antes = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM historico_estado WHERE activo_id=%s", (activo_id,))
        eventos_antes = cur.fetchone()[0]
        cur.execute("SELECT xmin::text FROM activo WHERE id=%s", (activo_id,))
        version_antes = cur.fetchone()[0]
    resultado = asyncio.run(ejecutar_iteracion(cliente.app.state.config, base[nombre]))
    assert resultado["ok"] is True
    with _conectar() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM metrica_historica WHERE activo_id=%s", (activo_id,))
        assert cur.fetchone()[0] == metricas_antes + resultado["metricas"]
        cur.execute("SELECT count(*) FROM historico_estado WHERE activo_id=%s", (activo_id,))
        assert cur.fetchone()[0] == eventos_antes
        cur.execute("SELECT ultima_actualizacion, xmin::text FROM activo WHERE id=%s", (activo_id,))
        fecha_activo, version_despues = cur.fetchone()
        assert fecha_activo is not None
        assert version_despues != version_antes


def test_cambios_de_estado_y_recuperacion(altas, base, cliente):
    import asyncio
    from etl.monitoreo import ejecutar_iteracion, leer_conexion, registrar_fallo
    activo_id = altas["aruba-cx-sw01"]["activo_id"]
    conexion_id = base["aruba-cx-sw01"]
    config = cliente.app.state.config
    with _conectar() as c, c.cursor() as cur:
        cur.execute("SELECT id, estado FROM puerto_switch WHERE switch_id=%s ORDER BY id LIMIT 1", (activo_id,))
        puerto_id, estado_puerto = cur.fetchone()
        cur.execute("UPDATE puerto_switch SET estado=%s WHERE id=%s",
                    ("Apagado" if estado_puerto == "Encendido" else "Encendido", puerto_id))
        cur.execute("UPDATE activo SET estado_operativo='Baja' WHERE id=%s", (activo_id,))
    resultado = asyncio.run(ejecutar_iteracion(config, conexion_id))
    assert resultado["ok"] and resultado["eventos"] >= 2
    with _conectar() as c, c.cursor() as cur:
        cur.execute("SELECT estado FROM puerto_switch WHERE id=%s", (puerto_id,))
        assert cur.fetchone()[0] == estado_puerto
        cur.execute("SELECT estado_operativo FROM activo WHERE id=%s", (activo_id,))
        assert cur.fetchone()[0] == altas["aruba-cx-sw01"]["estado_operativo"]
        cur.execute("SELECT ip_gestion FROM monitoreo_snmp WHERE id=%s", (conexion_id,))
        destino = cur.fetchone()[0]
        cur.execute("SELECT ultima_actualizacion FROM activo WHERE id=%s", (activo_id,))
        fecha_activo = cur.fetchone()[0]
        cur.execute("SELECT fecha_ultima_actualizacion FROM monitoreo_snmp WHERE id=%s", (conexion_id,))
        fecha_conexion = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM metrica_historica WHERE activo_id=%s", (activo_id,))
        metricas_antes = cur.fetchone()[0]
        cur.execute("UPDATE monitoreo_snmp SET ip_gestion='127.0.0.1:1' WHERE id=%s", (conexion_id,))
    try:
        fallo = asyncio.run(ejecutar_iteracion(config, conexion_id))
        assert fallo["ok"] is False and fallo["eventos"] == 1
        with _conectar() as c, c.cursor() as cur:
            cur.execute("SELECT estado_conexion, fecha_ultima_actualizacion FROM monitoreo_snmp WHERE id=%s", (conexion_id,))
            assert cur.fetchone() == ("Sin conexión", fecha_conexion)
            cur.execute("SELECT ultima_actualizacion FROM activo WHERE id=%s", (activo_id,))
            assert cur.fetchone()[0] == fecha_activo
            cur.execute("SELECT count(*) FROM metrica_historica WHERE activo_id=%s", (activo_id,))
            assert cur.fetchone()[0] == metricas_antes
        assert registrar_fallo(config, leer_conexion(config, conexion_id), "timeout")["eventos"] == 0
    finally:
        with _conectar() as c, c.cursor() as cur:
            cur.execute("UPDATE monitoreo_snmp SET ip_gestion=%s WHERE id=%s", (destino, conexion_id))
    recuperacion = asyncio.run(ejecutar_iteracion(config, conexion_id))
    assert recuperacion["ok"] and recuperacion["eventos"] == 1
    with _conectar() as c, c.cursor() as cur:
        cur.execute("SELECT campo, valor_nuevo FROM historico_estado WHERE activo_id=%s ORDER BY id DESC LIMIT 2", (activo_id,))
        assert cur.fetchall() == [("estado_conexion", "Activo"), ("estado_conexion", "Sin conexión")]


def test_componentes_nuevos_y_ausentes_y_campos_del_front(altas, base, cliente):
    import asyncio
    from etl.monitoreo import guardar_iteracion, leer_conexion
    from etl.ciclo import preparar_registro_activo
    from etl.snmp_cliente import ConexionSNMP
    from api.dto import separar_destino
    activo_id = altas["aruba-cx-sw01"]["activo_id"]
    config = cliente.app.state.config
    referencia = leer_conexion(config, base["aruba-cx-sw01"])
    host, puerto = separar_destino(referencia.ip_gestion)
    conexion = ConexionSNMP(host, puerto, referencia.usuario, referencia.clave,
                           referencia.clave_privacidad, config.snmp_context_name)
    ficha = asyncio.run(preparar_registro_activo(conexion, config, ip_gestion=referencia.ip_gestion))
    with _conectar() as c, c.cursor() as cur:
        cur.execute("UPDATE switch SET modo_operacion='L3' WHERE id=%s", (activo_id,))
        cur.execute("UPDATE activo SET responsable='Operaciones' WHERE id=%s", (activo_id,))
    nuevo = {"numero_puerto": "9/9/9", "velocidad": "1000 Mbps", "estado": "Encendido"}
    ficha["componentes"]["puerto_switch"].append(nuevo)
    agregado = guardar_iteracion(config, referencia, ficha)
    assert agregado["eventos"] == 1
    with _conectar() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM puerto_switch WHERE switch_id=%s AND numero_puerto='9/9/9'", (activo_id,))
        puerto_id = cur.fetchone()[0]
        cur.execute("SELECT modo_operacion FROM switch WHERE id=%s", (activo_id,))
        assert cur.fetchone()[0] == "L3"
        cur.execute("SELECT responsable FROM activo WHERE id=%s", (activo_id,))
        assert cur.fetchone()[0] == "Operaciones"
    ficha["componentes"]["puerto_switch"].pop()
    retirado = guardar_iteracion(config, referencia, ficha)
    assert retirado["eventos"] == 1
    with _conectar() as c, c.cursor() as cur:
        cur.execute("SELECT estado FROM puerto_switch WHERE id=%s", (puerto_id,))
        assert cur.fetchone()[0] == "Baja"


def test_slot_y_blade_conservan_su_vinculo(altas, base, cliente):
    import asyncio
    from etl.monitoreo import guardar_iteracion, leer_conexion
    from etl.ciclo import preparar_registro_activo
    from etl.snmp_cliente import ConexionSNMP
    from api.dto import separar_destino
    chasis_id = altas["hpe-c7000-01"]["activo_id"]
    blade_id = altas["hpe-bl460c-01"]["activo_id"]
    config = cliente.app.state.config
    referencia = leer_conexion(config, base["hpe-c7000-01"])
    host, puerto = separar_destino(referencia.ip_gestion)
    conexion = ConexionSNMP(host, puerto, referencia.usuario, referencia.clave,
                           referencia.clave_privacidad, config.snmp_context_name)
    ficha = asyncio.run(preparar_registro_activo(conexion, config, ip_gestion=referencia.ip_gestion))
    slot = next(s for s in ficha["componentes"]["chasis_slot"] if s["numero_slot"] == 1)
    original = slot.copy()
    slot.update(estado="LIBRE", hostname_servidor=None)
    assert guardar_iteracion(config, referencia, ficha)["eventos"] == 1
    with _conectar() as c, c.cursor() as cur:
        cur.execute("SELECT servidor_id FROM chasis_slot WHERE chasis_id=%s AND numero_slot=1", (chasis_id,))
        assert cur.fetchone()[0] is None
        cur.execute("SELECT id_chasis_slot FROM servidor WHERE id=%s", (blade_id,))
        assert cur.fetchone()[0] is None
    slot.update(original)
    assert guardar_iteracion(config, referencia, ficha)["eventos"] == 1
    with _conectar() as c, c.cursor() as cur:
        cur.execute("SELECT id, servidor_id FROM chasis_slot WHERE chasis_id=%s AND numero_slot=1", (chasis_id,))
        slot_id, servidor_id = cur.fetchone()
        assert servidor_id == blade_id
        cur.execute("SELECT id_chasis_slot FROM servidor WHERE id=%s", (blade_id,))
        assert cur.fetchone()[0] == slot_id
