from datetime import datetime
from unittest.mock import MagicMock

import pytest

from etl import monitoreo
from etl.config import cargar_configuracion
from tests.unitarios.test_eventos_componentes import preparar

FECHA = datetime(2026, 10, 13)


class Marcas:
    def __init__(self):
        self.filas = []
        self.ultima = None

    def execute(self, sql, params):
        if sql.startswith("SELECT id, valor_nuevo"):
            activo, tabla, campo, etiqueta = params
            matches = [f for f in self.filas if (f["activo"], f["tabla"], f["campo"], f["etiqueta"])
                       == (activo, tabla, campo, etiqueta)]
            self.ultima = matches[-1].copy() if matches else None
        elif "UPDATE historico_estado" in sql:
            valor, id_fila = ("0", params[0]) if "valor_nuevo='0'" in sql else params
            next(f for f in self.filas if f["id"] == id_fila)["valor_nuevo"] = valor
        else:
            pytest.fail(f"SQL inesperado: {sql}")

    def fetchone(self):
        return self.ultima


def entorno(monkeypatch, anteriores, limite=2):
    eventos = preparar(monkeypatch, anteriores)
    marcas = Marcas()
    def evento(cur, activo, campo, valor, descripcion, fecha, tabla=None, etiqueta=None):
        eventos.append((campo, valor, tabla, etiqueta))
        if campo == "lectura_componentes":
            marcas.filas.append({"id": len(marcas.filas) + 1, "activo": activo,
                                 "tabla": tabla, "campo": campo, "etiqueta": etiqueta,
                                 "valor_nuevo": valor})
    monkeypatch.setattr(monitoreo, "registrar_evento_estado", evento)
    omitted = []
    def proteger(tabla, padre, nuevas):
        omitida, cantidad = monitoreo._proteger_lectura_vacia(marcas, 19, tabla, padre, nuevas, FECHA, limite)
        if omitida:
            omitted.append(tabla)
        return omitida, cantidad
    def ejecutar(tabla, nuevas, padre=19):
        return monitoreo._reconciliar(marcas, 19, tabla, padre, nuevas, FECHA, proteger_lectura=proteger)
    return ejecutar, eventos, omitted, marcas


def discos():
    return [{"id": 7, "numero_serial": "DISCO-1", "estado": "Encendido"},
            {"id": 8, "numero_serial": "DISCO-2", "estado": "Encendido"}]


def test_primera_vacia_conserva_y_segunda_elimina_sin_eventos_de_baja(monkeypatch):
    filas = {"disco": discos()}
    ejecutar, eventos, omitidas, marcas = entorno(monkeypatch, filas)
    assert ejecutar("disco", []) == (0, 1)
    assert len(filas["disco"]) == 2
    assert omitidas == ["disco"]
    assert ejecutar("disco", []) == (2, 0)
    assert filas["disco"] == []
    assert [e[0] for e in eventos] == ["lectura_componentes"]
    assert ejecutar("disco", []) == (0, 0)


def test_lectura_identica_con_elementos_reinicia_confirmacion(monkeypatch):
    filas = {"disco": discos()}
    ejecutar, eventos, _, _ = entorno(monkeypatch, filas)
    assert ejecutar("disco", []) == (0, 1)
    nuevas = [{k: v for k, v in f.items() if k != "id"} for f in filas["disco"]]
    assert ejecutar("disco", nuevas) == (0, 1)
    assert ejecutar("disco", nuevas) == (0, 0)
    assert ejecutar("disco", []) == (0, 1)
    assert len(filas["disco"]) == 2
    assert [e[1] for e in eventos] == ["1", "0", "1"]


def test_uno_de_dos_se_retira_inmediatamente(monkeypatch):
    filas = {"disco": discos()}
    ejecutar, eventos, _, _ = entorno(monkeypatch, filas)
    assert ejecutar("disco", [{"numero_serial": "DISCO-2", "estado": "Encendido"}]) == (1, 0)
    assert [f["numero_serial"] for f in filas["disco"]] == ["DISCO-2"]
    assert eventos == []


def test_umbral_tres_no_duplica_aviso_y_contadores_independientes(monkeypatch):
    filas = {"disco": discos(), "ram": [{"id": 9, "numero_serial": "RAM", "estado": "Encendido"}]}
    ejecutar, eventos, _, _ = entorno(monkeypatch, filas, limite=3)
    assert ejecutar("disco", []) == (0, 1)
    assert ejecutar("ram", []) == (0, 1)
    assert ejecutar("disco", []) == (0, 0)
    assert len(filas["disco"]) == 2
    assert ejecutar("disco", []) == (2, 0)
    assert len(filas["ram"]) == 1
    assert len(eventos) == 2


def test_vacia_sin_componentes_no_genera_eventos(monkeypatch):
    ejecutar, eventos, omitidas, _ = entorno(monkeypatch, {"disco": []})
    assert ejecutar("disco", []) == (0, 0)
    assert eventos == omitidas == []


def test_slot_ocupado_no_se_modifica_en_primera_vacia(monkeypatch):
    slot = {"id": 7, "numero_slot": 1, "estado": "OCUPADO", "servidor_id": 33}
    filas = {"chasis_slot": [slot]}
    ejecutar, eventos, omitidas, _ = entorno(monkeypatch, filas)
    assert ejecutar("chasis_slot", []) == (0, 1)
    assert filas["chasis_slot"] == [slot]
    assert slot["servidor_id"] == 33
    assert omitidas == ["chasis_slot"]


def test_eliminar_nic_borra_primero_puertos():
    cursor = MagicMock()
    monitoreo._eliminar_componente(cursor, "tarjeta_red", 4, 19)
    assert cursor.execute.call_args_list[0].args == ("DELETE FROM puerto_tarjeta_red WHERE tarjeta_red_id=%s", (4,))
    assert cursor.execute.call_args_list[1].args == ("DELETE FROM tarjeta_red WHERE id=%s AND activo_id=%s", (4, 19))


@pytest.mark.parametrize("tabla", ["puerto_switch", "puerto_tarjeta_red"])
def test_puertos_ausentes_conservan_filas_y_ultimo_estado(monkeypatch, tabla):
    puerto = {"id": 7, "numero_puerto": "1", "estado": "Apagado"}
    filas = {tabla: [puerto]}
    ejecutar, eventos, _, _ = entorno(monkeypatch, filas)
    assert ejecutar(tabla, []) == (0, 1)
    assert ejecutar(tabla, []) == (0, 0)
    assert filas[tabla] == [puerto]
    assert [e[0] for e in eventos] == ["lectura_componentes"]


@pytest.mark.parametrize("tabla", sorted(monitoreo.ESTRUCTURALES))
def test_no_se_pueden_eliminar_filas_estructurales(tabla):
    with pytest.raises(monitoreo.DatosIncompletos, match="conservan sus filas"):
        monitoreo._eliminar_componente(MagicMock(), tabla, 7, 19)


@pytest.mark.parametrize("valor", ["0", "-1", "abc", "2.5"])
def test_configuracion_rechaza_umbral_invalido(monkeypatch, valor):
    monkeypatch.setattr("etl.config.load_dotenv", lambda *args: None)
    monkeypatch.setenv("ETL_API_KEY", "test")
    monkeypatch.setenv("LECTURAS_VACIAS_PARA_BAJA", valor)
    with pytest.raises(RuntimeError):
        cargar_configuracion()
