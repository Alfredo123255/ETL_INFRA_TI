"""Resuelve referencias existentes y verifica cambios concurrentes sin exponer claves."""
from dataclasses import dataclass, field
import psycopg2
from pydantic import SecretStr
from etl.db import conexion_bd
from etl.errores import ActivoDuplicado, DatosIncompletos, BaseNoDisponible, ReferenciaNoEncontrada

@dataclass(frozen=True)
class ReferenciasRegistro:
    conexion_id: int
    cluster_id: str
    datacenter: str
    ip_gestion: str
    usuario: str = field(repr=False)
    clave: SecretStr = field(repr=False)
    clave_privacidad: SecretStr | None = field(default=None, repr=False)

def leer_referencias(cursor, conexion_id, cluster_id, *, bloquear=False):
    cursor.execute("SELECT ip_gestion,usuario,clave,activo_id,clave_privacidad FROM monitoreo_snmp WHERE id=%s" +
                   (" FOR UPDATE" if bloquear else ""), (conexion_id,))
    row = cursor.fetchone()
    if row is None:
        raise ReferenciaNoEncontrada("La conexión indicada no existe.")
    ip, usuario, clave, activo_id, clave_privacidad = row
    if activo_id is not None:
        raise ActivoDuplicado("La conexión ya está vinculada a un activo.")
    cursor.execute("SELECT datacenter FROM clusters WHERE nombre=%s" +
                   (" FOR SHARE" if bloquear else ""), (cluster_id,))
    cluster = cursor.fetchone()
    if cluster is None:
        raise ReferenciaNoEncontrada("El clúster indicado no existe.")
    if not cluster[0]:
        raise DatosIncompletos("El clúster no tiene un datacenter asignado.")
    if not ip or not usuario or not clave:
        raise DatosIncompletos("La conexión no tiene credenciales completas.")
    return ReferenciasRegistro(conexion_id, cluster_id, cluster[0], ip, usuario, SecretStr(clave),
        SecretStr(clave_privacidad) if clave_privacidad else None)

def obtener_referencias(config, conexion_id, cluster_id):
    try:
        with conexion_bd(config) as connection:
            with connection.cursor() as cursor:
                return leer_referencias(cursor, conexion_id, cluster_id)
    except psycopg2.Error:
        raise BaseNoDisponible("No se pudieron consultar la conexión y el clúster.") from None

def bloquear_y_validar(connection, referencias):
    with connection.cursor() as cursor:
        actual = leer_referencias(cursor, referencias.conexion_id, referencias.cluster_id, bloquear=True)
        if actual != referencias:
            raise ActivoDuplicado("La conexión o el clúster cambiaron durante la consulta; vuelve a intentarlo.")

def vincular(connection, conexion_id, activo_id):
    with connection.cursor() as cursor:
        cursor.execute("""UPDATE monitoreo_snmp SET activo_id=%s, estado_conexion='Activo',
            fecha_ultima_actualizacion=CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
            WHERE id=%s AND activo_id IS NULL""", (activo_id, conexion_id))
        if cursor.rowcount != 1:
            raise ActivoDuplicado("La conexión ya no está disponible para vincular el activo.")
