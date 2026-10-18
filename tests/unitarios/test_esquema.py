from unittest.mock import MagicMock

import pytest

from etl.errores import BaseNoDisponible
from etl.esquema import verificar_columnas


def conexion(filas):
    db = MagicMock()
    db.cursor.return_value.__enter__.return_value.fetchall.return_value = filas
    return db


FILAS = [("monitoreo_snmp", "clave_privacidad", "character varying"),
         ("activo", "ultima_actualizacion", "timestamp without time zone")]


def test_verifica_instalacion_sin_ejecutar_migraciones():
    db = conexion(FILAS)
    assert verificar_columnas(db) == {"compatible": True, "columnas_verificadas": 2}
    sentencias = db.cursor.return_value.__enter__.return_value.execute.call_args_list
    assert len(sentencias) == 1 and sentencias[0].args[0].lstrip().startswith("SELECT")


@pytest.mark.parametrize("filas,detalle", [
    (FILAS[1:], "clave_privacidad"),
    (FILAS[:1] + [("activo", "ultima_actualizacion", "date")], "ultima_actualizacion"),
])
def test_informa_campo_ausente_o_fecha_sin_hora(filas, detalle):
    with pytest.raises(BaseNoDisponible, match=detalle):
        verificar_columnas(conexion(filas))
