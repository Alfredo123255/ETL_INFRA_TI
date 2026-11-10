"""Los contratos unitarios del cargador aislan la nueva evaluacion, probada con PostgreSQL."""
import pytest

@pytest.fixture(autouse=True)
def aislar_evaluacion_alertas(monkeypatch):
    import etl.carga as carga
    import etl.monitoreo as monitoreo
    import etl.programador as programador
    monkeypatch.setattr(carga, "evaluar_alertas", lambda *a, **k: {})
    monkeypatch.setattr(monitoreo, "evaluar_alertas", lambda *a, **k: {})
    monkeypatch.setattr(monitoreo, "cerrar_alertas_tarjeta", lambda *a, **k: None)
    monkeypatch.setattr(programador, "revisar_alertas", lambda *a, **k: None)
