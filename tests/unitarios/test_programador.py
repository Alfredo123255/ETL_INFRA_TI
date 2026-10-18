from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock
import pytest
import etl.programador as programador

from etl.programador import CANAL_ACTUALIZACION, conexiones_vencidas, solicitudes_inmediatas


def test_solicitud_actualiza_solo_el_equipo_pedido_sin_esperar_un_dia():
    ahora = datetime(2026, 10, 17, 12)
    filas = [(1, 86400, ahora), (2, 86400, ahora), (3, 60, ahora - timedelta(minutes=2))]
    assert conexiones_vencidas(filas, {2: ahora}, ahora, {2, 999}) == [2, 3]
    assert conexiones_vencidas(filas, {}, ahora) == [3]
    assert filas[0][1] == filas[1][1] == 86400


def test_aviso_duplicado_no_duplica_ciclo_y_descarta_identificadores_invalidos():
    guardia = SimpleNamespace(poll=Mock(), notifies=[
        SimpleNamespace(channel=CANAL_ACTUALIZACION, payload=valor)
        for valor in ("12", "12", "-1", "0", "abc", "1" * 40, "１２")])
    guardia.notifies.append(SimpleNamespace(channel="otro", payload="99"))
    assert solicitudes_inmediatas(guardia) == {12}
    assert guardia.notifies == []
    ahora = datetime(2026, 10, 17)
    assert conexiones_vencidas([(12, 1, None)], {}, ahora, {12}) == [12]


@pytest.mark.asyncio
async def test_arranque_recupera_avisos_perdidos_sin_duplicar_en_el_siguiente_tick(monkeypatch):
    class DetenerPrueba(Exception):
        pass
    guardia = MagicMock()
    guardia.notifies = []
    guardia.cursor.return_value.__enter__.return_value.fetchone.return_value = (True,)
    monkeypatch.setattr(programador, "obtener_conexion", lambda _: guardia)
    monkeypatch.setattr(programador, "verificar_columnas", lambda _: None)
    ultima = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    monkeypatch.setattr(programador, "conexiones_programadas", lambda *_: [(12, 86400, ultima)])
    ciclos, ticks = [], []
    async def ejecutar(_config, ids):
        ciclos.append(ids)
    async def tick(_segundos):
        ticks.append(1)
        if len(ticks) == 2:
            raise DetenerPrueba()
    monkeypatch.setattr(programador, "_ejecutar", ejecutar)
    monkeypatch.setattr(programador.asyncio, "sleep", tick)
    with pytest.raises(DetenerPrueba):
        await programador.iniciar_programador(None)
    assert ciclos == [[12]]
    guardia.close.assert_called_once()
