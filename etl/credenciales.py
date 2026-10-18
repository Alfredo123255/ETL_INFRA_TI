"""Cifrado autenticado interoperable con Java; la llave vive fuera de Git y de la BD."""
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr
from etl.errores import BaseNoDisponible

PREFIJO = "enc:v1:"


def _bytes(valor):
    return valor.get_secret_value() if isinstance(valor, SecretStr) else valor


def _llave(valor):
    try:
        texto = _bytes(valor)
        llave = base64.b64decode(texto, altchars=b"-_", validate=True)
        if len(llave) != 32:
            raise ValueError
        return llave
    except (ValueError, TypeError):
        raise BaseNoDisponible("La llave de cifrado SNMP no está configurada o no es válida.") from None


def cargar_llave():
    valor = os.getenv("SNMP_CREDENTIAL_KEY", "").strip()
    archivo = os.getenv("SNMP_CREDENTIAL_KEY_FILE", "").strip()
    if not valor and archivo:
        try:
            valor = Path(archivo).read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            raise BaseNoDisponible("No se puede leer el archivo de llave SNMP.") from None
    if not valor:
        return None  # Compatible con filas antiguas durante la conversión.
    _llave(valor)
    return SecretStr(valor)


def _aad(campo):
    if campo not in ("clave", "clave_privacidad"):
        raise ValueError("Campo de credencial no admitido")
    return f"infra-ti:monitoreo_snmp:{campo}:v1".encode()


def cifrar(valor, llave, campo="clave"):
    if valor is None:
        return None
    nonce = os.urandom(12)
    sobre = nonce + AESGCM(_llave(llave)).encrypt(nonce, _bytes(valor).encode("utf-8"), _aad(campo))
    resultado = PREFIJO + base64.urlsafe_b64encode(sobre).decode("ascii").rstrip("=")
    if len(resultado) > 255:
        raise BaseNoDisponible("La credencial cifrada supera el espacio disponible (máximo 158 bytes UTF-8).")
    return resultado


def descifrar(valor, llave, campo="clave"):
    if valor is None or not valor.startswith("enc:"):
        return valor  # Lectura transitoria de registros previos, nunca nuevas escrituras.
    key = _llave(llave)
    try:
        if not valor.startswith(PREFIJO):
            raise ValueError
        texto = valor[len(PREFIJO):]
        sobre = base64.b64decode(texto + "=" * (-len(texto) % 4), altchars=b"-_", validate=True)
        if len(sobre) < 28:
            raise ValueError
        return AESGCM(key).decrypt(sobre[:12], sobre[12:], _aad(campo)).decode("utf-8")
    except Exception:
        raise BaseNoDisponible("No se pudo descifrar la credencial SNMP; comprueba la llave externa.") from None
