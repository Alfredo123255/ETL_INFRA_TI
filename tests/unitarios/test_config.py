import asyncio
import secrets
from types import SimpleNamespace
import pytest
import etl.config as configuracion
import etl.programador as programador

@pytest.fixture
def entorno(monkeypatch):
    monkeypatch.setattr(configuracion, "load_dotenv", lambda *_: None)
    monkeypatch.setattr(configuracion, "cargar_llave", lambda: None)
    monkeypatch.setenv("ETL_API_KEY", secrets.token_urlsafe(24))
    monkeypatch.delenv("ETL_CONCURRENCIA", raising=False)

def test_concurrencia_predeterminada(entorno):
    assert configuracion.cargar_configuracion().etl_concurrencia == 20

@pytest.mark.parametrize("valor", ["1", "3", "32"])
def test_concurrencia_configurada(entorno, monkeypatch, valor):
    monkeypatch.setenv("ETL_CONCURRENCIA", valor)
    assert configuracion.cargar_configuracion().etl_concurrencia == int(valor)

@pytest.mark.parametrize("valor", ["0", "-1", "texto", "1.5", ""])
def test_concurrencia_invalida(entorno, monkeypatch, valor):
    monkeypatch.setenv("ETL_CONCURRENCIA", valor)
    with pytest.raises(RuntimeError, match="ETL_CONCURRENCIA"):
        configuracion.cargar_configuracion()

@pytest.mark.asyncio
async def test_programador_respeta_el_maximo_configurado(monkeypatch):
    activos = maximo = completados = 0
    async def iteracion(_config, _id):
        nonlocal activos, maximo, completados
        activos += 1
        maximo = max(maximo, activos)
        await asyncio.sleep(0.01)
        activos -= 1
        completados += 1
        return {}
    monkeypatch.setattr(programador, "ejecutar_iteracion", iteracion)
    await programador._ejecutar(SimpleNamespace(etl_concurrencia=3), range(8))
    assert maximo == 3
    assert completados == 8
