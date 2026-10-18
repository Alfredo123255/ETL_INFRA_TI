import base64
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr
from etl.credenciales import cargar_llave, cifrar, descifrar
from etl.errores import BaseNoDisponible

LLAVE = SecretStr(base64.urlsafe_b64encode(bytes(32)).decode())


def test_sobre_aleatorio_separado_por_campo_y_unicode():
    valor = "Contraseña prueba Ñ-123"
    primero = cifrar(valor, LLAVE)
    segundo = cifrar(valor, LLAVE)
    assert primero != segundo
    assert valor not in primero
    assert descifrar(primero, LLAVE) == valor
    with pytest.raises(BaseNoDisponible):
        descifrar(primero, LLAVE, "clave_privacidad")


@pytest.mark.parametrize("alteracion", ["llave", "tag", "version", "sin_llave"])
def test_falla_sin_exponer_secreto(alteracion):
    valor = cifrar("Enterprise", LLAVE)
    llave = LLAVE
    if alteracion == "llave": llave = SecretStr(base64.urlsafe_b64encode(bytes([1])*32).decode())
    if alteracion == "sin_llave": llave = None
    if alteracion == "tag": valor = valor[:-2] + ("AA" if valor[-2:] != "AA" else "BB")
    if alteracion == "version": valor = valor.replace("v1", "v2")
    with pytest.raises(BaseNoDisponible) as error:
        descifrar(valor, llave)
    assert "Enterprise" not in str(error.value)
    assert valor not in str(error.value)


def test_limite_sin_cambiar_varchar_y_filas_anteriores():
    assert len(cifrar("x"*158, LLAVE, "clave_privacidad")) <= 255
    with pytest.raises(BaseNoDisponible): cifrar("x"*159, LLAVE)
    assert descifrar("anterior", None) == "anterior"
    assert descifrar(None, None) is None


def test_llave_externa_no_se_imprime(tmp_path, monkeypatch):
    archivo = tmp_path / "llave"
    archivo.write_text(LLAVE.get_secret_value())
    monkeypatch.delenv("SNMP_CREDENTIAL_KEY", raising=False)
    monkeypatch.setenv("SNMP_CREDENTIAL_KEY_FILE", str(archivo))
    llave = cargar_llave()
    assert llave == LLAVE
    assert LLAVE.get_secret_value() not in repr(llave)


def test_lectura_monitoreo_descifra_para_snmp():
    from etl.config import Configuracion
    from etl.monitoreo import leer_conexion
    config = Configuracion(SecretStr("test"), credential_key=LLAVE)
    cursor = MagicMock()
    cursor.fetchone.return_value = (1, "127.0.0.1:161", "HPE", cifrar("Enterprise", LLAVE),
                                    cifrar("Enterprise", LLAVE, "clave_privacidad"))
    db = MagicMock()
    db.cursor.return_value.__enter__.return_value = cursor
    with patch("etl.monitoreo.conexion_bd") as conexion:
        conexion.return_value.__enter__.return_value = db
        referencia = leer_conexion(config, 2)
    assert referencia.clave.get_secret_value() == "Enterprise"
    assert referencia.clave_privacidad.get_secret_value() == "Enterprise"
    assert "Enterprise" not in repr(referencia)
