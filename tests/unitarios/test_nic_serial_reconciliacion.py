"""Agregar un serial a una NIC existente no representa una baja y alta física."""
from datetime import datetime

import etl.monitoreo as monitoreo


def test_nic_sin_serial_conserva_id_y_no_genera_evento(monkeypatch):
    anterior = {"id": 7, "activo_id": 6, "numero_serial": None,
                "modelo": "HPE Ethernet 331i", "estado": "Encendido"}
    actualizaciones = []

    def filas(_cur, tabla, _relacion, _padre_id):
        return [anterior] if tabla == "tarjeta_red" else []

    def actualizar(_cur, tabla, fila_id, _anterior, datos, **_kwargs):
        actualizaciones.append((tabla, fila_id, datos["numero_serial"]))
        return {"numero_serial": datos["numero_serial"]}

    monkeypatch.setattr(monitoreo, "_filas", filas)
    monkeypatch.setattr(monitoreo, "_actualizar_fila", actualizar)
    monkeypatch.setattr(monitoreo, "_insertar", lambda *_args: (_ for _ in ()).throw(
        AssertionError("No debe insertar una tarjeta nueva")))
    monkeypatch.setattr(monitoreo, "_evento", lambda *_args: (_ for _ in ()).throw(
        AssertionError("No debe registrar un cambio de estado")))

    cambios, eventos = monitoreo._reconciliar(
        None, 6, "tarjeta_red", 6,
        [{"numero_serial": "SIM-DL380-NIC-001", "modelo": "HPE Ethernet 331i",
          "estado": "Encendido", "puertos": []}], datetime(2026, 10, 5))

    assert (cambios, eventos) == (1, 0)
    assert actualizaciones == [("tarjeta_red", 7, "SIM-DL380-NIC-001")]
