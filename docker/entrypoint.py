"""Construye la URL PostgreSQL sin perder contraseñas que contienen símbolos."""
import os
import sys
from urllib.parse import quote


def preparar_entorno(entorno):
    resultado = dict(entorno)
    for nombre in ('ETL_API_KEY', 'SNMP_CREDENTIAL_KEY_FILE'):
        if not resultado.get(nombre, '').strip():
            raise RuntimeError(f'Falta configurar {nombre}.')
    if not resultado.get('DATABASE_URL', '').strip():
        for nombre in ('DB_HOST', 'DB_NAME', 'DB_USERNAME', 'DB_PASSWORD'):
            if not resultado.get(nombre, ''):
                raise RuntimeError(f'Falta configurar {nombre}.')
        usuario = quote(resultado['DB_USERNAME'], safe='')
        clave = quote(resultado['DB_PASSWORD'], safe='')
        base = quote(resultado['DB_NAME'], safe='')
        host = resultado['DB_HOST']
        puerto = int(resultado.get('DB_PORT', '5432'))
        if not 1 <= puerto <= 65535:
            raise RuntimeError('DB_PORT inválido.')
        if ':' in host and not host.startswith('['):
            host = '[' + host + ']'
        resultado['DATABASE_URL'] = f'postgresql://{usuario}:{clave}@{host}:{puerto}/{base}'
    return resultado


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Falta el comando del servicio.')
    try:
        entorno = preparar_entorno(os.environ)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from None
    os.execvpe(sys.argv[1], sys.argv[1:], entorno)


if __name__ == '__main__':
    main()
