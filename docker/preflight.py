"""Valida AWS, esquema y llave con transacción de solo lectura; no ejecuta ciclos."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.config import cargar_configuracion
from etl.credenciales import descifrar
from etl.db import obtener_conexion
from etl.esquema import verificar_columnas


def verificar(config):
    db = obtener_conexion(config)
    try:
        db.set_session(readonly=True)
        resultado = verificar_columnas(db)
        with db.cursor() as cur:
            cur.execute('SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()')
            fila = cur.fetchone()
            if not fila or not fila[0]:
                raise RuntimeError('PostgreSQL no está usando TLS.')
            cur.execute('SELECT clave, clave_privacidad FROM public.monitoreo_snmp')
            filas = cur.fetchall()
            cifradas = 0
            for clave, privacidad in filas:
                for campo, valor in [('clave', clave), ('clave_privacidad', privacidad)]:
                    if valor and valor.startswith('enc:'):
                        descifrar(valor, config.credential_key, campo)
                        cifradas += 1
            cur.execute("SELECT count(*) FROM public.activo")
            activos = cur.fetchone()[0]
        return resultado | {'tls': True, 'conexiones': len(filas),
                            'credenciales_cifradas_verificadas': cifradas, 'activos': activos}
    finally:
        db.rollback()
        db.close()


def main():
    try:
        print(json.dumps(verificar(cargar_configuracion())))
    except Exception:
        # No emitir URL, contraseña ni detalles internos del controlador PostgreSQL.
        print('Verificación fallida: revisa acceso AWS/TLS, esquema y llave original.', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
