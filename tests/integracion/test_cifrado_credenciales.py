"""Conversión real con rollback, exclusivamente en una base test sin conexiones previas."""
import base64
from contextlib import contextmanager
import os
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg2
import pytest
from pydantic import SecretStr

from etl.config import Configuracion
from etl.credenciales import cifrar, descifrar
from etl.errores import BaseNoDisponible
from etl.migrar_credenciales import convertir


def test_conversion_atomica_idempotente_y_verificacion_sin_cambiar_datos(monkeypatch):
    url = os.getenv('TEST_DATABASE_URL','')
    if not url: pytest.skip('Falta TEST_DATABASE_URL')
    assert 'test' in urlsplit(url).path.lower()
    assert url != os.getenv('DATABASE_URL')
    llave = SecretStr(base64.urlsafe_b64encode(bytes(32)).decode())
    config = Configuracion(SecretStr('test'),database_url=SecretStr(url),credential_key=llave)
    ids = []
    marca = 'CIFRADO-'+uuid4().hex
    try:
        with psycopg2.connect(url) as db, db.cursor() as cur:
            for i,clave in enumerate(('Enterprise','enc:v1:invalido')):
                cur.execute("""INSERT INTO monitoreo_snmp(ip_gestion,usuario,clave,clave_privacidad,
                    frecuencia_actualizacion,estado_conexion) VALUES (%s,'test',%s,'Enterprise',86400,'Inactivo') RETURNING id""",
                    (marca+str(i),clave))
                ids.append(cur.fetchone()[0])
        # El adaptador limita únicamente el SELECT a las filas de esta fixture.
        # Las escrituras, commits y rollbacks usan PostgreSQL real sin DDL.
        from etl.db import conexion_bd
        class CursorFixture:
            def __init__(self, cursor): self.cursor = cursor
            def __enter__(self): self.cursor.__enter__(); return self
            def __exit__(self, *args): return self.cursor.__exit__(*args)
            def execute(self, sql, params=None):
                if sql == 'SELECT id,clave,clave_privacidad FROM monitoreo_snmp ORDER BY id FOR UPDATE':
                    return self.cursor.execute('SELECT id,clave,clave_privacidad FROM monitoreo_snmp WHERE id=ANY(%s) ORDER BY id FOR UPDATE',(ids,))
                return self.cursor.execute(sql,params)
            def fetchall(self): return self.cursor.fetchall()
        class ConexionFixture:
            def __init__(self, db): self.db = db
            def cursor(self): return CursorFixture(self.db.cursor())
        @contextmanager
        def aislada(conf):
            with conexion_bd(conf) as db: yield ConexionFixture(db)
        monkeypatch.setattr('etl.migrar_credenciales.conexion_bd',aislada)
        with pytest.raises(BaseNoDisponible): convertir(config)
        with psycopg2.connect(url) as db, db.cursor() as cur:
            cur.execute('SELECT clave FROM monitoreo_snmp WHERE id=%s',(ids[0],))
            assert cur.fetchone()[0] == 'Enterprise'  # La primera actualización también se revirtió.
            cur.execute('UPDATE monitoreo_snmp SET clave=%s WHERE id=%s',
                        (cifrar('Admin@9000',llave),ids[1]))
        assert convertir(config) == {'conexiones_revisadas':2,'convertidas':2}
        with psycopg2.connect(url) as db, db.cursor() as cur:
            cur.execute('SELECT clave,clave_privacidad,estado_conexion,frecuencia_actualizacion FROM monitoreo_snmp WHERE id=ANY(%s) ORDER BY id',(ids,))
            antes = cur.fetchall()
        assert descifrar(antes[0][0],llave) == 'Enterprise'
        assert descifrar(antes[1][0],llave) == 'Admin@9000'
        assert all(descifrar(f[1],llave,'clave_privacidad')=='Enterprise' for f in antes)
        assert all(f[2:]==('Inactivo',86400) for f in antes)
        assert convertir(config) == {'conexiones_revisadas':2,'convertidas':0}
        assert convertir(config,verificar=True) == {'conexiones_revisadas':2,'pendientes':0}
        with psycopg2.connect(url) as db, db.cursor() as cur:
            cur.execute('SELECT clave,clave_privacidad,estado_conexion,frecuencia_actualizacion FROM monitoreo_snmp WHERE id=ANY(%s) ORDER BY id',(ids,))
            assert cur.fetchall() == antes
    finally:
        if ids:
            with psycopg2.connect(url) as db, db.cursor() as cur:
                cur.execute('DELETE FROM monitoreo_snmp WHERE id=ANY(%s)',(ids,))
