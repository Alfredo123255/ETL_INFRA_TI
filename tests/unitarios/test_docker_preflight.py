"""Verificación previa con esquema vigente; BD simulada y secretos efímeros."""
import base64
import os
import secrets
from types import SimpleNamespace
from unittest.mock import MagicMock

from pydantic import SecretStr
import pytest

from docker import preflight
from etl.credenciales import cifrar
from etl.errores import BaseNoDisponible


def llave():
    return SecretStr(base64.urlsafe_b64encode(os.urandom(32)).decode())


def preparar(monkeypatch, filas=(), tls=True):
    db = MagicMock()
    cur = db.cursor.return_value.__enter__.return_value
    consultas = []
    def ejecutar(consulta):
        assert 'clave_privacidad' not in consulta
        consultas.append(consulta)
        if consulta == 'SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()':
            cur.fetchone.return_value = (tls,)
        elif consulta == 'SELECT clave FROM public.monitoreo_snmp':
            cur.fetchall.return_value = filas
        elif consulta == 'SELECT count(*) FROM public.activo':
            cur.fetchone.return_value = (28,)
        else:
            pytest.fail('Consulta no prevista en la verificación previa')
    cur.execute.side_effect = ejecutar
    monkeypatch.setattr(preflight,'obtener_conexion',lambda _:db)
    monkeypatch.setattr(preflight,'verificar_columnas',lambda _: {'compatible':True,'columnas_verificadas':1})
    return db, consultas


def test_verifica_unica_clave_cifrada_y_conserva_lecturas_de_filas_antiguas(monkeypatch):
    key = llave()
    filas = [(cifrar(secrets.token_urlsafe(18),key),),(secrets.token_urlsafe(18),),(None,),('',)]
    db, consultas = preparar(monkeypatch,filas)
    resultado = preflight.verificar(SimpleNamespace(credential_key=key))
    assert resultado == {'compatible':True,'columnas_verificadas':1,'tls':True,
        'conexiones':4,'credenciales_cifradas_verificadas':1,'activos':28}
    assert consultas[1] == 'SELECT clave FROM public.monitoreo_snmp'
    db.set_session.assert_called_once_with(readonly=True)
    db.rollback.assert_called_once()
    db.close.assert_called_once()


def test_rechaza_llave_incorrecta_sin_exponer_credencial_y_cierra_conexion(monkeypatch):
    valor = secrets.token_urlsafe(18)
    cifrada = cifrar(valor,llave())
    db, _ = preparar(monkeypatch,[(cifrada,)])
    with pytest.raises(BaseNoDisponible) as exc:
        preflight.verificar(SimpleNamespace(credential_key=llave()))
    assert valor not in str(exc.value) and cifrada not in str(exc.value)
    db.rollback.assert_called_once()
    db.close.assert_called_once()


def test_sigue_exigiendo_tls_antes_de_leer_credenciales(monkeypatch):
    db, consultas = preparar(monkeypatch,tls=False)
    with pytest.raises(RuntimeError,match='TLS'):
        preflight.verificar(SimpleNamespace(credential_key=llave()))
    assert len(consultas) == 1
    db.rollback.assert_called_once()
    db.close.assert_called_once()


def test_base_sin_conexiones_snmp_es_valida(monkeypatch):
    db, _ = preparar(monkeypatch)
    resultado = preflight.verificar(SimpleNamespace(credential_key=llave()))
    assert resultado['conexiones'] == resultado['credenciales_cifradas_verificadas'] == 0
    db.rollback.assert_called_once()
    db.close.assert_called_once()
