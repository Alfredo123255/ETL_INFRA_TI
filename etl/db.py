"""Conexiones PostgreSQL y transacciones; trabaja sobre el esquema existente."""
from contextlib import contextmanager
import psycopg2
from etl.errores import BaseNoDisponible


def obtener_conexion(config):
    if config.database_url is None:
        raise BaseNoDisponible("Falta configurar DATABASE_URL para registrar activos.")
    try:
        return psycopg2.connect(config.database_url.get_secret_value(),
            connect_timeout=config.db_timeout,
            options="-c statement_timeout=15000 -c lock_timeout=5000")
    except psycopg2.Error:
        raise BaseNoDisponible("No se pudo conectar con PostgreSQL.") from None


@contextmanager
def conexion_bd(config):
    conexion = obtener_conexion(config)
    try:
        yield conexion
        conexion.commit()
    except BaseException:
        try:
            conexion.rollback()
        except psycopg2.Error:
            pass
        raise
    finally:
        conexion.close()
