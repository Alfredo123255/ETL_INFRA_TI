"""Acceso SQL del monitoreo; usa exclusivamente el cursor y la transacción del llamador."""
from etl.errores import DatosIncompletos
from etl.repositorio import COLUMNAS

RELACION = {"puerto_switch": "switch_id", "chasis_slot": "chasis_id", "puerto_tarjeta_red": "tarjeta_red_id"}
TABLAS_SUBTIPO = frozenset(("servidor", "switch", "storage", "chasis_blade"))
TABLAS_COMPONENTES = frozenset(COLUMNAS) - TABLAS_SUBTIPO - {"activo", "historico_estado"}
ESTRUCTURALES = frozenset(("puerto_switch", "puerto_tarjeta_red", "chasis_slot"))


def _validar_componente(tabla, relacion=None):
    if tabla not in TABLAS_COMPONENTES or (relacion is not None and relacion != RELACION.get(tabla, "activo_id")):
        raise DatosIncompletos("Tabla o relación de componente no permitida.")


def leer_conexion_habilitada(cur, conexion_id):
    cur.execute("""SELECT m.activo_id, m.ip_gestion, m.usuario, m.clave
            FROM monitoreo_snmp m JOIN activo a ON a.id=m.activo_id
            WHERE m.id=%s AND a.estado_operativo <> 'Baja' AND NOT a.mantenimiento_activo
            AND m.estado_conexion IN ('Activo', 'Sin conexión')""", (conexion_id,))
    return cur.fetchone()


def bloquear_componentes(cur, tabla, relacion, padre_id):
    if relacion is None:
        raise DatosIncompletos("Relación de componente no permitida.")
    _validar_componente(tabla, relacion)
    cur.execute(f"SELECT * FROM {tabla} WHERE {relacion}=%s ORDER BY id FOR UPDATE", (padre_id,))
    return list(cur.fetchall())


def actualizar_fila(cur, tabla, fila_id, escritura):
    if tabla not in COLUMNAS:
        raise DatosIncompletos("Tabla de actualización no permitida.")
    permitidas = set(COLUMNAS[tabla]) - {"id", "activo_id", "switch_id", "chasis_id", "tarjeta_red_id"}
    if set(escritura) - permitidas:
        raise DatosIncompletos("Columna de actualización no permitida.")
    if not escritura:
        return
    columnas = list(escritura)
    cur.execute(f"UPDATE {tabla} SET {', '.join(k + '=%s' for k in columnas)} WHERE id=%s", (*[escritura[k] for k in columnas], fila_id))


def eliminar_puertos_tarjeta(cur, fila_id):
    cur.execute("DELETE FROM puerto_tarjeta_red WHERE tarjeta_red_id=%s", (fila_id,))


def eliminar_componente(cur, tabla, fila_id, padre_id):
    _validar_componente(tabla)
    if tabla in ESTRUCTURALES:
        raise DatosIncompletos("Los puertos y slots estructurales conservan sus filas.")
    relacion = RELACION.get(tabla, "activo_id")
    cur.execute(f"DELETE FROM {tabla} WHERE id=%s AND {relacion}=%s", (fila_id, padre_id))


def listar_discos_ausentes(cur, activo_id, series):
    cur.execute("""SELECT id, numero_serial FROM disco
        WHERE activo_id=%s AND numero_serial = ANY(%s) FOR UPDATE""", (activo_id, series))
    return cur.fetchall()


def eliminar_disco(cur, fila_id, activo_id):
    cur.execute("DELETE FROM disco WHERE id=%s AND activo_id=%s", (fila_id, activo_id))


def leer_slots_chasis(cur, chasis_id):
    cur.execute("""SELECT s.id, s.servidor_id, s.hostname_servidor, s.estado,
        a.ubicacion FROM chasis_slot s JOIN activo a ON a.id=s.chasis_id
        WHERE s.chasis_id=%s ORDER BY s.id FOR UPDATE OF s""", (chasis_id,))
    return cur.fetchall()


def buscar_blades_en_ubicacion(cur, hostname, ubicacion):
    cur.execute("""SELECT b.id FROM activo b JOIN servidor v ON v.id=b.id AND v.tipo='BLADE'
                WHERE b.hostname=%s AND b.ubicacion=%s""", (hostname, ubicacion))
    return cur.fetchall()


def liberar_slot(cur, servidor_id, slot_id):
    cur.execute("UPDATE servidor SET id_chasis_slot=NULL WHERE id=%s AND id_chasis_slot=%s", (servidor_id, slot_id))
    cur.execute("UPDATE chasis_slot SET servidor_id=NULL WHERE id=%s", (slot_id,))


def leer_asignacion_blade(cur, servidor_id):
    cur.execute("SELECT id_chasis_slot FROM servidor WHERE id=%s FOR UPDATE", (servidor_id,))
    return cur.fetchone()


def asignar_slot(cur, servidor_id, slot_id):
    cur.execute("UPDATE servidor SET id_chasis_slot=%s WHERE id=%s", (slot_id, servidor_id))
    cur.execute("UPDATE chasis_slot SET servidor_id=%s WHERE id=%s", (servidor_id, slot_id))


def bloquear_conexion(cur, conexion_id):
    cur.execute("""SELECT activo_id, ip_gestion, usuario, clave, estado_conexion
        FROM monitoreo_snmp WHERE id=%s FOR UPDATE""", (conexion_id,))
    return cur.fetchone()


def bloquear_estado_operativo(cur, activo_id):
    cur.execute("SELECT estado_operativo FROM activo WHERE id=%s FOR UPDATE", (activo_id,))
    return cur.fetchone()


def marcar_conexion_sin_conexion(cur, conexion_id):
    cur.execute("UPDATE monitoreo_snmp SET estado_conexion='Sin conexión' WHERE id=%s", (conexion_id,))


def bloquear_activo(cur, activo_id):
    cur.execute("SELECT * FROM activo WHERE id=%s FOR UPDATE", (activo_id,))
    return cur.fetchone()


def bloquear_subtipo(cur, subtipo, activo_id):
    if subtipo not in TABLAS_SUBTIPO:
        raise DatosIncompletos("Subtipo de activo no permitido.")
    cur.execute(f"SELECT * FROM {subtipo} WHERE id=%s FOR UPDATE", (activo_id,))
    return cur.fetchone()


def marcar_conexion_activa(cur, conexion_id):
    cur.execute("""UPDATE monitoreo_snmp SET estado_conexion='Activo' WHERE id=%s""", (conexion_id,))


