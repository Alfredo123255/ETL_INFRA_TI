"""Validación de identificadores y conservación de la comparación previa a la escritura."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from etl import monitoreo, repositorio_monitoreo as repo
from etl.errores import DatosIncompletos


@pytest.mark.parametrize("tabla,relacion", [
    ("disco; DROP TABLE activo", "activo_id"), ("desconocida", "activo_id"),
    ("activo", "activo_id"), ("disco", "id"), ("disco", None), ("puerto_switch", "activo_id"),
    ("chasis_slot", "chasis_id OR TRUE"), ("tarjeta_red", "tarjeta_red_id")])
def test_bloqueo_rechaza_identificadores_ajenos_a_la_lista_blanca(tabla, relacion):
    cur = MagicMock()
    with pytest.raises(DatosIncompletos):
        repo.bloquear_componentes(cur, tabla, relacion, 1)
    cur.execute.assert_not_called()


@pytest.mark.parametrize("tabla,datos", [
    ("disco; DELETE FROM activo", {"estado": "Encendido"}),
    ("inexistente", {"estado": "Encendido"}),
    ("disco", {"id": 2}), ("disco", {"activo_id": 2}),
    ("disco", {"estado = NULL; DELETE FROM activo": None})])
def test_actualizacion_rechaza_tabla_o_columnas_no_permitidas(tabla, datos):
    cur = MagicMock()
    with pytest.raises(DatosIncompletos):
        repo.actualizar_fila(cur, tabla, 1, datos)
    cur.execute.assert_not_called()


@pytest.mark.parametrize("tabla", ["activo", "historico_estado", "desconocida", *sorted(repo.ESTRUCTURALES)])
def test_eliminacion_rechaza_tablas_ajenas_y_filas_estructurales(tabla):
    cur = MagicMock()
    with pytest.raises(DatosIncompletos):
        repo.eliminar_componente(cur, tabla, 1, 2)
    cur.execute.assert_not_called()


@pytest.mark.parametrize("tabla", ["disco", "activo", "servidor; DELETE FROM activo"])
def test_bloqueo_subtipo_rechaza_identificadores_no_permitidos(tabla):
    cur = MagicMock()
    with pytest.raises(DatosIncompletos):
        repo.bloquear_subtipo(cur, tabla, 1)
    cur.execute.assert_not_called()


def test_sin_cambios_no_ejecuta_actualizacion_y_el_redondeo_no_genera_falsos_cambios(monkeypatch):
    escribir = MagicMock()
    monkeypatch.setattr(repo, "actualizar_fila", escribir)
    assert monitoreo._actualizar_fila(None, "cpu", 1,
        {"velocidad_ghz": Decimal("3.89")}, {"velocidad_ghz": 3.888}) == {}
    escribir.assert_not_called()
    cambios = monitoreo._actualizar_fila(None, "cpu", 1,
        {"velocidad_ghz": Decimal("3.88")}, {"velocidad_ghz": 3.888})
    assert cambios == {"velocidad_ghz": Decimal("3.89")}
    escribir.assert_called_once_with(None, "cpu", 1, cambios)


def test_fecha_exitosa_forzada_se_escribe_incluso_sin_cambios(monkeypatch):
    fecha = datetime(2026, 1, 2, 12)
    escribir = MagicMock()
    monkeypatch.setattr(repo, "actualizar_fila", escribir)
    assert monitoreo._actualizar_fila(None, "activo", 1,
        {"ultima_actualizacion": fecha}, {"ultima_actualizacion": fecha},
        forzar=("ultima_actualizacion",)) == {}
    escribir.assert_called_once_with(None, "activo", 1, {"ultima_actualizacion": fecha})


def test_eliminar_tarjeta_coordina_cierre_y_dependencias_en_el_orden_original(monkeypatch):
    llamadas = []
    monkeypatch.setattr(monitoreo, "cerrar_alertas_tarjeta", lambda *a: llamadas.append("alertas"))
    monkeypatch.setattr(repo, "eliminar_puertos_tarjeta", lambda *a: llamadas.append("puertos"))
    monkeypatch.setattr(repo, "eliminar_componente", lambda *a: llamadas.append("tarjeta"))
    monitoreo._eliminar_componente(None, "tarjeta_red", 1, 2)
    assert llamadas == ["alertas", "puertos", "tarjeta"]
