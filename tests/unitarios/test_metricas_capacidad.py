from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from etl.metricas import construir_metricas
from etl.errores import DatosIncompletos
from etl.normalizacion.storage import normalizar_storage
from tests.unitarios.test_huawei import captura


@pytest.mark.parametrize("agente,marca", [
    ("hpe-storage-fc-01", "HPE"), ("hpe-storage-fc-02", "HPE"),
    ("huawei-dorado-01", "Huawei"), ("huawei-dorado-02", "Huawei")])
def test_storage_guarda_capacidad_en_cada_lectura_aunque_no_cambie(agente, marca):
    fecha = datetime(2026, 10, 25, 14)
    ficha = normalizar_storage(captura(agente), fecha_actualizacion=fecha, fabricante=marca)
    esperado = ficha["storage"]["capacidad_total_tb"] - ficha["storage"]["capacidad_usada_tb"]
    for momento in (fecha, fecha + timedelta(minutes=2)):
        filas = construir_metricas("STORAGE", ficha, momento)
        valores = {m["nombre_metrica"]: m["valor"] for m in filas}
        assert valores["almacenamiento_uso_tb"] == ficha["storage"]["capacidad_usada_tb"]
        assert not {"capacidad_total_tb", "capacidad_libre_tb", "capacidad_libre_pct"} & valores.keys()
        assert all(m["fecha_medicion"] == momento for m in filas)


def test_capacidad_usada_ausente_no_se_inventa_como_cero():
    filas = construir_metricas("STORAGE", {"storage": {"capacidad_total_tb": 20}}, datetime.now())
    assert filas == []


def test_cero_es_valido_sin_porcentaje_por_division_entre_cero():
    filas = construir_metricas("STORAGE", {"storage": {
        "capacidad_total_tb": 0, "capacidad_usada_tb": 0}}, datetime.now())
    assert {f["nombre_metrica"]: f["valor"] for f in filas} == {
        "almacenamiento_uso_tb": Decimal(0)}


@pytest.mark.parametrize("total,usado", [(20, 21), (-1, 0), (20, -1), (float("nan"), 1)])
def test_rechaza_capacidades_invalidas(total, usado):
    with pytest.raises(DatosIncompletos):
        construir_metricas("STORAGE", {"storage": {
            "capacidad_total_tb": total, "capacidad_usada_tb": usado}}, datetime.now())
