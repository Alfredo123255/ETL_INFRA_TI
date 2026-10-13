"""Historial de componentes sin conexión a la base de datos."""
from datetime import datetime, timezone

import pytest

from etl import monitoreo, repositorio


FECHA = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def preparar(monkeypatch, anteriores):
    eventos = []

    def filas(_cur, tabla, _relacion, _padre_id):
        # Cada SELECT devuelve una instantánea; un UPDATE no modifica el dict ya leído.
        return [fila.copy() for fila in anteriores.get(tabla, [])]

    def actualizar(_cur, tabla, fila_id, anterior, datos, **_kwargs):
        cambios = {k: v for k, v in datos.items() if anterior.get(k) != v}
        next(fila for fila in anteriores[tabla] if fila["id"] == fila_id).update(cambios)
        return cambios

    def evento(_cur, activo_id, campo, valor, descripcion, fecha,
               componente_tipo=None, componente_sn=None):
        eventos.append((activo_id, campo, valor, descripcion, fecha,
                        componente_tipo, componente_sn))

    monkeypatch.setattr(monitoreo, "_filas", filas)
    monkeypatch.setattr(monitoreo, "_actualizar_fila", actualizar)
    monkeypatch.setattr(monitoreo, "registrar_evento_estado", evento)
    return eventos


@pytest.mark.parametrize("tabla,identificador,valor,anterior,nuevo", [
    ("cpu", "numero_serial", "CPU-1", "Encendido", "Degradado"),
    ("ram", "numero_serial", "RAM-1", "Encendido", "Degradado"),
    ("disco", "numero_serial", "DISCO-1", "Encendido", "Degradado"),
    ("controladora_raid", "numero_serial", "RAID-1", "Encendido", "Degradado"),
    ("fuente_poder", "numero_serial", "PSU-1", "Encendido", "Apagado"),
    ("ventilador", "numero_serial", "FAN-1", "Encendido", "Degradado"),
    ("tarjeta_red", "numero_serial", "NIC-1", "Encendido", "Degradado"),
    ("puerto_switch", "numero_puerto", "1/1/1", "Encendido", "Apagado"),
    ("puerto_tarjeta_red", "numero_puerto", "1", "Encendido", "Apagado"),
    ("chasis_slot", "numero_slot", 1, "OCUPADO", "LIBRE"),
])
def test_cambio_de_estado_registra_un_evento_y_no_lo_duplica(
        monkeypatch, tabla, identificador, valor, anterior, nuevo):
    fila = {"id": 7, identificador: valor, "estado": anterior}
    eventos = preparar(monkeypatch, {tabla: [fila]})
    datos = {identificador: valor, "estado": nuevo}

    assert monitoreo._reconciliar(None, 19, tabla, 19, [datos], FECHA) == (1, 1)
    assert monitoreo._reconciliar(None, 19, tabla, 19, [datos], FECHA) == (0, 0)
    assert len(eventos) == 1
    activo_id, campo, estado, descripcion, fecha, tipo, etiqueta = eventos[0]
    assert (activo_id, campo, estado, fecha, tipo) == (19, "estado", nuevo, FECHA, tabla)
    assert etiqueta == (str(valor) if identificador == "numero_serial"
                        else f"{identificador}:{valor}")
    assert f"{anterior} → {nuevo}" in descripcion


@pytest.mark.parametrize("tabla,clave,valor", [
    ("cpu", "numero_serial", "CPU-1"),
    ("ram", "numero_serial", "RAM-1"),
    ("disco", "numero_serial", "DISCO-1"),
    ("controladora_raid", "numero_serial", "RAID-1"),
    ("fuente_poder", "numero_serial", "PSU-1"),
    ("ventilador", "numero_serial", "FAN-1"),
    ("tarjeta_red", "numero_serial", "NIC-1"),
    ("puerto_switch", "numero_puerto", "1/1/1"),
    ("puerto_tarjeta_red", "numero_puerto", "1"),
])
def test_componente_ausente_conserva_ultimo_estado(monkeypatch, tabla, clave, valor):
    fila = {"id": 7, clave: valor, "estado": "Encendido"}
    eventos = preparar(monkeypatch, {tabla: [fila]})

    assert monitoreo._reconciliar(None, 19, tabla, 19, [], FECHA) == (0, 0)
    assert monitoreo._reconciliar(None, 19, tabla, 19, [], FECHA) == (0, 0)
    assert fila["estado"] == "Encendido"
    assert eventos == []


def test_disco_con_bahia_vacia_sale_del_inventario_y_conserva_evento(monkeypatch):
    class Cursor:
        def __init__(self):
            self.consultas = []

        def execute(self, sql, params):
            self.consultas.append((sql, params))

        def fetchall(self):
            return [{"id": 7, "numero_serial": "DISCO-1"}]

    eventos = []
    monkeypatch.setattr(monitoreo, "registrar_evento_estado",
        lambda *args: eventos.append(args))
    cur = Cursor()
    assert monitoreo._retirar_discos_confirmados(
        cur, 19, ["DISCO-1"], [{"numero_serial": "DISCO-2"}], FECHA) == 1
    assert any("DELETE FROM disco" in sql for sql, _ in cur.consultas)
    assert eventos[0][1:3] == (19, "presencia")
    assert eventos[0][3] == "Ausente"
    assert eventos[0][-2:] == ("disco", "DISCO-1")


def test_no_elimina_disco_sin_serie_identificable_o_aun_presente(monkeypatch):
    monkeypatch.setattr(monitoreo, "registrar_evento_estado",
        lambda *_args: pytest.fail("No debería registrar evento"))

    class Cursor:
        def execute(self, *_args):
            pytest.fail("No debería consultar ni borrar discos")

    assert monitoreo._retirar_discos_confirmados(
        Cursor(), 19, [None, ""], [], FECHA) == 0
    assert monitoreo._retirar_discos_confirmados(
        Cursor(), 19, ["DISCO-1"], [{"numero_serial": "DISCO-1"}], FECHA) == 0


def test_slot_ausente_queda_libre_una_sola_vez(monkeypatch):
    fila = {"id": 7, "numero_slot": 1, "estado": "OCUPADO"}
    eventos = preparar(monkeypatch, {"chasis_slot": [fila]})

    assert monitoreo._reconciliar(None, 19, "chasis_slot", 19, [], FECHA) == (1, 1)
    assert monitoreo._reconciliar(None, 19, "chasis_slot", 19, [], FECHA) == (0, 0)
    assert fila["estado"] == "LIBRE"
    assert [(e[1], e[2], e[5]) for e in eventos] == [("estado", "LIBRE", "chasis_slot")]


def test_baja_no_es_estado_valido_de_un_componente(monkeypatch):
    fila = {"id": 7, "numero_serial": "DISCO-1", "estado": "Encendido"}
    eventos = preparar(monkeypatch, {"disco": [fila]})

    with pytest.raises(monitoreo.DatosIncompletos, match="Baja solo aplica a activos"):
        monitoreo._reconciliar(None, 19, "disco", 19,
                              [{"numero_serial": "DISCO-1", "estado": "Baja"}], FECHA)
    assert fila["estado"] == "Encendido"
    assert eventos == []


def test_componente_nuevo_y_cambio_solo_de_modelo(monkeypatch):
    eventos = preparar(monkeypatch, {"disco": []})
    monkeypatch.setattr(monitoreo, "_insertar", lambda *_args: 8)
    nuevo = {"numero_serial": "DISCO-2", "modelo": "SSD", "estado": "Encendido"}
    assert monitoreo._reconciliar(None, 19, "disco", 19, [nuevo], FECHA) == (1, 1)
    assert eventos[0][2] == "Encendido"
    assert "sin estado previo → Encendido" in eventos[0][3]

    fila = {"id": 8, **nuevo}
    eventos = preparar(monkeypatch, {"disco": [fila]})
    assert monitoreo._reconciliar(None, 19, "disco", 19,
                                  [{**nuevo, "modelo": "SSD nuevo"}], FECHA) == (1, 0)
    assert eventos == []


def test_puerto_de_tarjeta_registra_su_propio_evento(monkeypatch):
    nic = {"id": 4, "numero_serial": "NIC-1", "estado": "Encendido"}
    puerto = {"id": 5, "numero_puerto": "1", "estado": "Encendido"}
    eventos = preparar(monkeypatch, {"tarjeta_red": [nic], "puerto_tarjeta_red": [puerto]})
    nueva = {"numero_serial": "NIC-1", "estado": "Encendido",
             "puertos": [{"numero_puerto": "1", "estado": "Apagado"}]}

    assert monitoreo._reconciliar(None, 19, "tarjeta_red", 19, [nueva], FECHA) == (1, 1)
    assert [(e[1], e[2], e[5], e[6]) for e in eventos] == [
        ("estado", "Apagado", "puerto_tarjeta_red", "numero_puerto:1")]


def test_evento_de_componente_guarda_tipo_identificador_y_fecha(monkeypatch):
    guardados = []
    monkeypatch.setattr(repositorio, "_insertar",
                        lambda _cur, tabla, datos: guardados.append((tabla, datos)))
    repositorio.registrar_evento_estado(None, 19, "estado", "Degradado",
                                        "CPU degradada", FECHA, "cpu", "CPU-1")
    assert guardados == [("historico_estado", {
        "activo_id": 19, "componente_tipo": "cpu", "componente_sn": "CPU-1",
        "campo": "estado", "valor_nuevo": "Degradado",
        "descripcion": "CPU degradada", "fecha_cambio": FECHA,
    })]
