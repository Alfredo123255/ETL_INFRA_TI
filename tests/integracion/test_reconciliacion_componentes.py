"""Reconciliación contra el esquema existente de una BD test; cada prueba hace rollback."""
import copy
from contextlib import contextmanager
from datetime import datetime
import os
from urllib.parse import urlparse
from uuid import uuid4

import psycopg2
from pydantic import SecretStr
import pytest

from etl import monitoreo
from etl.config import Configuracion

pytestmark = pytest.mark.integracion


@pytest.fixture
def entorno(monkeypatch):
    monkeypatch.setattr(monitoreo, "CONTADORES_LECTURA", {})
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("Falta TEST_DATABASE_URL")
    if "test" not in urlparse(url).path.lower():
        pytest.fail("Se requiere una base de prueba")
    db = psycopg2.connect(url)
    @contextmanager
    def conexion(_config):
        with db.cursor() as cur:
            cur.execute("SAVEPOINT iteracion_componentes")
        try:
            yield db
        except Exception:
            with db.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT iteracion_componentes")
            raise
        finally:
            with db.cursor() as cur:
                cur.execute("RELEASE SAVEPOINT iteracion_componentes")
    monkeypatch.setattr(monitoreo, "conexion_bd", conexion)
    marca = "COMP-TEST-" + uuid4().hex[:12]
    with db.cursor() as cur:
        cur.execute("INSERT INTO datacenters(nombre) VALUES (%s)", (marca,))

    class Entorno:
        config = Configuracion(SecretStr("test"), database_url=SecretStr(url))

        def crear(self, tipo="SERVIDOR", subtipo="RACKEABLE"):
            nombre = marca + "-" + uuid4().hex[:6]
            with db.cursor() as cur:
                cur.execute("""INSERT INTO activo(numero_serie,hostname,ubicacion,tipo_activo,
                    estado_operativo,ultima_actualizacion) VALUES (%s,%s,%s,%s,'Encendido',%s)
                    RETURNING id""", (nombre, nombre, marca, tipo, datetime(2026, 1, 1)))
                activo_id = cur.fetchone()[0]
                if tipo == "SERVIDOR":
                    cur.execute("INSERT INTO servidor(id,tipo) VALUES (%s,%s)", (activo_id, subtipo))
                    datos_subtipo, tabla = {"tipo": subtipo}, "servidor"
                elif tipo == "CHASIS":
                    cur.execute("INSERT INTO chasis_blade(id,cantidad_slots) VALUES (%s,2)", (activo_id,))
                    datos_subtipo, tabla = {"cantidad_slots": 2}, "chasis_blade"
                elif tipo == "STORAGE":
                    cur.execute("INSERT INTO storage(id) VALUES (%s)", (activo_id,))
                    datos_subtipo, tabla = {}, "storage"
                else:
                    cur.execute("INSERT INTO switch(id) VALUES (%s)", (activo_id,))
                    datos_subtipo, tabla = {}, "switch"
                cur.execute("""INSERT INTO monitoreo_snmp(ip_gestion,usuario,clave,
                    frecuencia_actualizacion,estado_conexion,activo_id)
                    VALUES ('127.0.0.1:1','test','test',60,'Activo',%s) RETURNING id""", (activo_id,))
                conexion_id = cur.fetchone()[0]
            referencia = monitoreo.ConexionMonitoreo(conexion_id, activo_id, "127.0.0.1:1", "test", SecretStr("test"), None)
            ficha = {"activo": {"numero_serie": nombre, "hostname": nombre, "ubicacion": marca,
                                "tipo_activo": tipo, "estado_operativo": "Encendido"},
                     tabla: datos_subtipo, "componentes": {}, "mediciones": []}
            return referencia, ficha

        def sql(self, consulta, params=()):
            with db.cursor() as cur:
                cur.execute(consulta, params)
                return cur.fetchall() if cur.description else []

        def discos(self, activo_id):
            return self.sql("SELECT numero_serial FROM disco WHERE activo_id=%s ORDER BY numero_serial", (activo_id,))

        def guardar(self, referencia, ficha, componentes):
            nueva = copy.deepcopy(ficha)
            nueva["componentes"] = componentes
            return monitoreo.guardar_iteracion(self.config, referencia, nueva)

    try:
        yield Entorno()
    finally:
        db.rollback()
        db.close()


DISCOS = [{"numero_serial": "D1", "estado": "Encendido"}, {"numero_serial": "D2", "estado": "Encendido"}]


def test_vacia_conserva_segunda_elimina_y_reinstalacion_inserta(entorno):
    ref, ficha = entorno.crear()
    entorno.guardar(ref, ficha, {"disco": DISCOS})
    r = entorno.guardar(ref, ficha, {"disco": []})
    assert r["tablas_omitidas"] == ["disco"]
    assert entorno.discos(ref.activo_id) == [("D1",), ("D2",)]
    assert entorno.sql("SELECT componente_sn FROM historico_estado WHERE activo_id=%s AND campo='presencia' AND valor_nuevo='Retirado'", (ref.activo_id,)) == []
    r = entorno.guardar(ref, ficha, {"disco": []})
    assert r["tablas_omitidas"] == []
    assert entorno.discos(ref.activo_id) == []
    assert entorno.sql("SELECT componente_sn FROM historico_estado WHERE activo_id=%s AND campo='presencia' AND valor_nuevo='Retirado' ORDER BY componente_sn", (ref.activo_id,)) == [("D1",), ("D2",)]
    assert entorno.sql("SELECT campo,valor_nuevo FROM historico_estado WHERE activo_id=%s AND campo IN ('presencia','estado') AND valor_nuevo IN ('Baja','Ausente')", (ref.activo_id,)) == []
    assert entorno.guardar(ref, ficha, {"disco": []})["eventos"] == 0
    entorno.guardar(ref, ficha, {"disco": [DISCOS[0]]})
    assert entorno.discos(ref.activo_id) == [("D1",)]
    assert entorno.sql("SELECT count(*) FROM historico_estado WHERE activo_id=%s AND campo='presencia' AND valor_nuevo='Agregado' AND componente_sn='D1'", (ref.activo_id,)) == [(2,)]
    assert entorno.guardar(ref, ficha, {"disco": [DISCOS[0]]})["eventos"] == 0


def test_recuperacion_identica_reinicia_y_lista_parcial_elimina(entorno):
    ref, ficha = entorno.crear()
    entorno.guardar(ref, ficha, {"disco": DISCOS})
    entorno.guardar(ref, ficha, {"disco": []})
    entorno.guardar(ref, ficha, {"disco": DISCOS})
    r = entorno.guardar(ref, ficha, {"disco": []})
    assert r["tablas_omitidas"] == ["disco"]
    assert len(entorno.discos(ref.activo_id)) == 2
    entorno.guardar(ref, ficha, {"disco": [DISCOS[1]]})
    assert entorno.discos(ref.activo_id) == [("D2",)]


def test_vacia_sin_componentes_no_registra_aviso(entorno):
    ref, ficha = entorno.crear()
    r = entorno.guardar(ref, ficha, {"disco": []})
    assert r["eventos"] == 0
    assert r["tablas_omitidas"] == []


def test_puertos_nic_conservados_y_eliminar_nic_limpia_dependencias(entorno):
    ref, ficha = entorno.crear()
    nics = [{"numero_serial": "N1", "estado": "Encendido", "puertos": [
        {"numero_puerto": "1", "estado": "Encendido"}, {"numero_puerto": "2", "estado": "Apagado"}]},
        {"numero_serial": "N2", "estado": "Encendido", "puertos": []}]
    entorno.guardar(ref, ficha, {"tarjeta_red": nics})
    vacia = copy.deepcopy(nics)
    vacia[0]["puertos"] = []
    assert entorno.guardar(ref, ficha, {"tarjeta_red": vacia})["tablas_omitidas"] == ["puerto_tarjeta_red"]
    entorno.guardar(ref, ficha, {"tarjeta_red": vacia})
    assert entorno.sql("SELECT p.numero_puerto,p.estado FROM puerto_tarjeta_red p JOIN tarjeta_red n ON n.id=p.tarjeta_red_id WHERE n.activo_id=%s ORDER BY p.numero_puerto", (ref.activo_id,)) == [("1", "Encendido"), ("2", "Apagado")]
    entorno.guardar(ref, ficha, {"tarjeta_red": [nics[1]]})
    assert entorno.sql("SELECT numero_serial FROM tarjeta_red WHERE activo_id=%s", (ref.activo_id,)) == [("N2",)]
    assert entorno.sql("SELECT p.id FROM puerto_tarjeta_red p JOIN tarjeta_red n ON n.id=p.tarjeta_red_id WHERE n.activo_id=%s", (ref.activo_id,)) == []


def test_puertos_switch_apagados_no_desaparecen(entorno):
    ref, ficha = entorno.crear("SWITCH")
    puertos = [{"numero_puerto": "1/1/1", "estado": "Encendido"}, {"numero_puerto": "1/1/2", "estado": "Apagado"}]
    entorno.guardar(ref, ficha, {"puerto_switch": puertos})
    entorno.guardar(ref, ficha, {"puerto_switch": [puertos[0]]})
    entorno.guardar(ref, ficha, {"puerto_switch": []})
    entorno.guardar(ref, ficha, {"puerto_switch": []})
    assert entorno.sql("SELECT numero_puerto,estado FROM puerto_switch WHERE switch_id=%s ORDER BY numero_puerto", (ref.activo_id,)) == [("1/1/1", "Encendido"), ("1/1/2", "Apagado")]


def test_slot_conserva_vinculo_primera_vacia_y_fila_libre_segunda(entorno):
    chasis, ficha = entorno.crear("CHASIS")
    blade, ficha_blade = entorno.crear("SERVIDOR", "BLADE")
    slots = [{"numero_slot": 1, "estado": "OCUPADO", "hostname_servidor": ficha_blade["activo"]["hostname"]},
             {"numero_slot": 2, "estado": "LIBRE", "hostname_servidor": None}]
    entorno.guardar(chasis, ficha, {"chasis_slot": slots})
    previo = entorno.sql("SELECT id,servidor_id FROM chasis_slot WHERE chasis_id=%s AND numero_slot=1", (chasis.activo_id,))[0]
    assert previo[1] == blade.activo_id
    entorno.guardar(chasis, ficha, {"chasis_slot": []})
    assert entorno.sql("SELECT id,servidor_id FROM chasis_slot WHERE chasis_id=%s AND numero_slot=1", (chasis.activo_id,))[0] == previo
    assert entorno.sql("SELECT id_chasis_slot FROM servidor WHERE id=%s", (blade.activo_id,)) == [(previo[0],)]
    entorno.guardar(chasis, ficha, {"chasis_slot": []})
    assert entorno.sql("SELECT numero_slot,estado,servidor_id FROM chasis_slot WHERE chasis_id=%s ORDER BY numero_slot", (chasis.activo_id,)) == [(1, "LIBRE", None), (2, "LIBRE", None)]
    assert entorno.sql("SELECT id_chasis_slot FROM servidor WHERE id=%s", (blade.activo_id,)) == [(None,)]


def test_rollback_si_componentes_incompatibles(entorno):
    ref, ficha = entorno.crear()
    entorno.guardar(ref, ficha, {"disco": DISCOS})
    with pytest.raises(monitoreo.DatosIncompletos, match="incompatibles"):
        entorno.guardar(ref, ficha, {"puerto_switch": []})
    assert len(entorno.discos(ref.activo_id)) == 2


def test_error_despues_de_retirar_componente_revierte_el_borrado(entorno):
    ref, ficha = entorno.crear()
    entorno.guardar(ref, ficha, {"disco": DISCOS})
    eventos_antes = entorno.sql("SELECT campo,valor_nuevo,componente_sn FROM historico_estado WHERE activo_id=%s ORDER BY id", (ref.activo_id,))
    with pytest.raises(monitoreo.DatosIncompletos, match="Baja solo aplica a activos"):
        entorno.guardar(ref, ficha, {"disco": [DISCOS[0]],
            "ram": [{"numero_serial": "R1", "estado": "Baja"}]})
    assert entorno.discos(ref.activo_id) == [("D1",), ("D2",)]
    assert entorno.sql("SELECT campo,valor_nuevo,componente_sn FROM historico_estado WHERE activo_id=%s ORDER BY id", (ref.activo_id,)) == eventos_antes


def test_confirmacion_puertos_independiente_por_tarjeta(entorno):
    ref, ficha = entorno.crear()
    nics = [{"numero_serial": nombre, "estado": "Encendido", "puertos": [
        {"numero_puerto": "1", "estado": "Apagado"}]} for nombre in ("N1", "N2")]
    entorno.guardar(ref, ficha, {"tarjeta_red": nics})
    nics[0]["puertos"] = []
    assert entorno.guardar(ref, ficha, {"tarjeta_red": nics})["tablas_omitidas"] == ["puerto_tarjeta_red"]
    assert entorno.guardar(ref, ficha, {"tarjeta_red": nics})["tablas_omitidas"] == []
    assert len(entorno.sql("SELECT p.id FROM puerto_tarjeta_red p JOIN tarjeta_red n ON n.id=p.tarjeta_red_id WHERE n.activo_id=%s", (ref.activo_id,))) == 2


@pytest.mark.parametrize("tipo,tabla", [
    (tipo, tabla) for tipo, tablas in monitoreo.COMPATIBLES.items()
    for tabla in tablas if tabla not in monitoreo.ESTRUCTURALES
])
def test_agregado_y_retiro_se_conservan_sin_duplicarse_en_todos_los_tipos(entorno, tipo, tabla):
    ref, ficha = entorno.crear(tipo)
    piezas = [{"numero_serial": serie, "estado": "Encendido"} for serie in ("P1", "P2", "P3")]
    entorno.guardar(ref, ficha, {tabla: piezas[:2]})
    assert entorno.guardar(ref, ficha, {tabla: piezas[:2]})["eventos"] == 0
    resultado = entorno.guardar(ref, ficha, {tabla: piezas[1:]})
    assert resultado["eventos"] == 3  # incorporación, estado inicial y retiro
    assert entorno.sql(f"SELECT numero_serial FROM {tabla} WHERE activo_id=%s ORDER BY numero_serial", (ref.activo_id,)) == [("P2",), ("P3",)]
    eventos = entorno.sql("""SELECT componente_tipo,componente_sn,valor_nuevo,fecha_cambio
        FROM historico_estado WHERE activo_id=%s AND campo='presencia' ORDER BY id""", (ref.activo_id,))
    assert [(e[0], e[1], e[2]) for e in eventos] == [
        (tabla, "P1", "Agregado"), (tabla, "P2", "Agregado"),
        (tabla, "P3", "Agregado"), (tabla, "P1", "Retirado")]
    assert all(isinstance(e[3], datetime) for e in eventos)
    assert entorno.guardar(ref, ficha, {tabla: piezas[1:]})["eventos"] == 0
    assert entorno.sql("SELECT count(*) FROM historico_estado WHERE activo_id=%s AND campo='presencia'", (ref.activo_id,)) == [(4,)]


def test_retiro_de_tarjeta_deja_su_evento_y_no_un_retiro_por_cada_puerto(entorno):
    ref, ficha = entorno.crear()
    nics = [{"numero_serial": serie, "estado": "Encendido", "puertos": [
        {"numero_puerto": "1", "estado": "Apagado"}]} for serie in ("N1", "N2")]
    entorno.guardar(ref, ficha, {"tarjeta_red": nics})
    resultado = entorno.guardar(ref, ficha, {"tarjeta_red": nics[1:]})
    assert resultado["eventos"] == 1
    assert entorno.sql("SELECT numero_serial FROM tarjeta_red WHERE activo_id=%s", (ref.activo_id,)) == [("N2",)]
    assert entorno.sql("SELECT count(*) FROM puerto_tarjeta_red p JOIN tarjeta_red n ON n.id=p.tarjeta_red_id WHERE n.activo_id=%s", (ref.activo_id,)) == [(1,)]
    assert entorno.sql("SELECT componente_tipo,componente_sn FROM historico_estado WHERE activo_id=%s AND campo='presencia' AND valor_nuevo='Retirado'", (ref.activo_id,)) == [("tarjeta_red", "N1")]


def test_confirmacion_revertida_no_se_cuenta_y_no_escribe_diagnosticos(entorno):
    ref, ficha = entorno.crear()
    entorno.guardar(ref, ficha, {"disco": DISCOS})
    with pytest.raises(monitoreo.DatosIncompletos):
        entorno.guardar(ref, ficha, {"disco": [], "ram": [{"numero_serial": "R", "estado": "Baja"}]})
    assert entorno.guardar(ref, ficha, {"disco": []})["tablas_omitidas"] == ["disco"]
    assert len(entorno.discos(ref.activo_id)) == 2
    assert entorno.guardar(ref, ficha, {"disco": []})["tablas_omitidas"] == []
    assert entorno.discos(ref.activo_id) == []
    assert entorno.sql("SELECT id FROM historico_estado WHERE activo_id=%s AND campo='lectura_componentes'", (ref.activo_id,)) == []


def test_reinicio_del_programador_exige_nueva_confirmacion(entorno):
    ref, ficha = entorno.crear()
    entorno.guardar(ref, ficha, {"disco": DISCOS})
    assert entorno.guardar(ref, ficha, {"disco": []})["tablas_omitidas"] == ["disco"]
    monitoreo.CONTADORES_LECTURA.clear()
    assert entorno.guardar(ref, ficha, {"disco": []})["tablas_omitidas"] == ["disco"]
    assert len(entorno.discos(ref.activo_id)) == 2


def test_baja_no_se_reactiva_aunque_la_conexion_quede_activa(entorno, monkeypatch):
    from etl.programador import conexiones_programadas

    ref, ficha = entorno.crear()
    entorno.sql("UPDATE activo SET estado_operativo='Baja' WHERE id=%s", (ref.activo_id,))
    assert entorno.guardar(ref, ficha, {"disco": DISCOS}) == {"conexion_id": ref.id, "omitida": True}
    assert monitoreo.registrar_fallo(entorno.config, ref, "timeout")["eventos"] == 0
    assert monitoreo.leer_conexion(entorno.config, ref.id) is None
    # Este entorno comparte una transacción para que cada prueba revierta sus datos.
    import etl.programador as programador
    monkeypatch.setattr(programador, "conexion_bd", monitoreo.conexion_bd)
    assert conexiones_programadas(entorno.config, ref.id) == []
    assert entorno.sql("SELECT estado_operativo FROM activo WHERE id=%s", (ref.activo_id,)) == [("Baja",)]
    assert entorno.sql("SELECT estado_conexion FROM monitoreo_snmp WHERE id=%s", (ref.id,)) == [("Activo",)]
    assert entorno.sql("SELECT id FROM historico_estado WHERE activo_id=%s", (ref.activo_id,)) == []
