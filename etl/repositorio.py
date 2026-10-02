"""SQL parametrizado de registro inicial; no administra el esquema."""
from etl.errores import DatosIncompletos

COLUMNAS = {
    "activo": ("numero_serie", "hostname", "fabricante", "modelo", "generacion", "ubicacion",
        "ip_gestion", "tipo_activo", "estado_operativo", "version_firmware",
        "ultima_actualizacion", "temperatura", "consumo_electrico_w", "cluster"),
    "servidor": ("id", "ip_sistema_operativo", "version_so", "tipo"),
    "switch": ("id", "tipo_red", "cantidad_puertos", "cantidad_puertos_ocupados", "modo_operacion"),
    "storage": ("id", "protocolo_comunicacion", "capacidad_total_tb", "capacidad_usada_tb", "iops"),
    "chasis_blade": ("id", "cantidad_slots"),
    "chasis_slot": ("chasis_id", "numero_slot", "estado", "hostname_servidor"),
    "puerto_switch": ("switch_id", "numero_puerto", "velocidad", "estado"),
    "cpu": ("activo_id", "numero_serial", "familia", "marca", "modelo", "velocidad_ghz",
        "cantidad_nucleos", "cantidad_hilos", "cache_l1_mb", "cache_l2_mb", "cache_l3_mb", "estado"),
    "ram": ("activo_id", "numero_serial", "marca", "modelo", "generacion", "velocidad_mhz", "capacidad_gb", "estado"),
    "disco": ("activo_id", "numero_serial", "marca", "tipo", "capacidad_gb", "velocidad_rpm", "estado", "modelo"),
    "tarjeta_red": ("activo_id", "numero_serial", "marca", "modelo", "estado", "cantidad_puertos"),
    "puerto_tarjeta_red": ("tarjeta_red_id", "numero_puerto", "mac_address", "velocidad", "estado"),
    "fuente_poder": ("activo_id", "numero_serial", "modelo", "consumo_w", "tipo_corriente", "estado"),
    "ventilador": ("activo_id", "numero_serial", "velocidad_rpm", "modelo", "estado"),
    "controladora_raid": ("activo_id", "modelo", "raid", "numero_serial", "estado"),
    "historico_estado": ("activo_id", "componente_tipo", "componente_sn", "campo", "valor_nuevo",
        "descripcion", "fecha_cambio"),
}

# Vocabulario de historico_estado.campo: exactamente los nombres de las columnas que cambian
# ("estado_operativo" en activo, "estado_conexion" en monitoreo_snmp). El futuro ciclo automático
# debe reutilizar estas constantes para comparar y registrar cambios.
CAMPO_ESTADO_OPERATIVO = "estado_operativo"
CAMPO_ESTADO_CONEXION = "estado_conexion"
ESTADO_CONEXION_VINCULADA = "Activo"  # el valor que vincular() deja en monitoreo_snmp
# Textos fijos: nunca incluyen IP, usuario, claves ni datos del equipo.
DESCRIPCION_ESTADO_INICIAL = "Estado inicial al registrar el activo"
DESCRIPCION_CONEXION_VINCULADA = "Conexión SNMP vinculada al registrar el activo"


def _insertar(cursor, tabla, datos):
    permitidas = COLUMNAS[tabla]
    if set(datos) - set(permitidas):
        raise DatosIncompletos("La ficha contiene campos incompatibles con el esquema.")
    columnas = [columna for columna in permitidas if columna in datos]
    if not columnas:
        raise DatosIncompletos("Faltan datos para guardar la ficha.")
    # Tabla y columnas solo proceden de la lista fija; los valores siempre son parámetros.
    sql = f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({', '.join(['%s'] * len(columnas))}) RETURNING id"
    cursor.execute(sql, tuple(datos[columna] for columna in columnas))
    fila = cursor.fetchone()
    return fila["id"] if isinstance(fila, dict) else fila[0]


def crear_activo(conexion, ficha):
    """Inserta activo, subtipo y componentes en la transacción del llamador."""
    activo = ficha["activo"]
    subtipo={"SERVIDOR":"servidor","SWITCH":"switch","STORAGE":"storage","CHASIS":"chasis_blade"}.get(activo["tipo_activo"])
    if subtipo is None or subtipo not in ficha:
        raise DatosIncompletos("La ficha no corresponde a un tipo de activo conocido.")
    with conexion.cursor() as cursor:
        cursor.execute("SELECT nombre FROM datacenters WHERE nombre = %s", (activo["ubicacion"],))
        if cursor.fetchone() is None:
            raise DatosIncompletos("La ubicación no corresponde a un datacenter registrado.")
        cursor.execute("INSERT INTO modelos (nombre_modelo) VALUES (%s) ON CONFLICT (nombre_modelo) DO NOTHING",
                       (activo["modelo"],))
        activo_id = _insertar(cursor, "activo", activo)
        _insertar(cursor, subtipo, {"id": activo_id, **ficha[subtipo]})
        cantidades = {}
        compatibles={"SERVIDOR":("cpu","ram","disco","tarjeta_red","fuente_poder","ventilador","controladora_raid"),
            "STORAGE":("cpu","ram","disco","tarjeta_red","fuente_poder","ventilador","controladora_raid"),
            "SWITCH":("puerto_switch","cpu","ram","fuente_poder","ventilador"),
            "CHASIS":("chasis_slot","tarjeta_red","fuente_poder","ventilador")}
        for tabla, filas in ficha["componentes"].items():
            if tabla not in compatibles[activo["tipo_activo"]]:
                raise DatosIncompletos("Tipo de componente incompatible con el activo.")
            cantidades[tabla] = len(filas)
            for fila in filas:
                puertos = fila.get("puertos", []) if tabla == "tarjeta_red" else []
                datos = {campo: valor for campo, valor in fila.items() if campo != "puertos"}
                relacion = {"puerto_switch":"switch_id","chasis_slot":"chasis_id"}.get(tabla,"activo_id")
                componente_id = _insertar(cursor, tabla, {**datos, relacion: activo_id})
                if tabla == "tarjeta_red":
                    cantidades["puerto_tarjeta_red"] = cantidades.get("puerto_tarjeta_red", 0) + len(puertos)
                    for puerto in puertos:
                        _insertar(cursor, "puerto_tarjeta_red", {**puerto, "tarjeta_red_id": componente_id})
        cantidades.setdefault("puerto_tarjeta_red", 0)
        if activo["tipo_activo"] in ("SERVIDOR", "CHASIS"):
            vincular_slot_blade(cursor, activo_id, activo)
    return activo_id, cantidades


def vincular_slot_blade(cursor, activo_id, activo):
    """Vincula un blade y su slot si el otro activo ya existe en el mismo clúster."""
    if activo["tipo_activo"] == "SERVIDOR":
        cursor.execute("SELECT tipo FROM servidor WHERE id=%s", (activo_id,))
        if cursor.fetchone()[0] != "BLADE":
            return
        cursor.execute("""SELECT s.id, s.servidor_id FROM chasis_slot s
            JOIN activo c ON c.id=s.chasis_id
            WHERE s.hostname_servidor=%s AND c.cluster=%s AND c.ubicacion=%s
            FOR UPDATE OF s""", (activo["hostname"],activo.get("cluster"),activo["ubicacion"]))
        matches=cursor.fetchall()
        if len(matches)>1:
            raise DatosIncompletos("El servidor blade coincide con varios slots de chasis.")
        if matches:
            slot_id, asignado=matches[0]
            if asignado not in (None,activo_id):
                raise DatosIncompletos("El slot ya está asignado a otro servidor.")
            cursor.execute("UPDATE servidor SET id_chasis_slot=%s WHERE id=%s", (slot_id,activo_id))
            cursor.execute("UPDATE chasis_slot SET servidor_id=%s WHERE id=%s", (activo_id,slot_id))
    elif activo["tipo_activo"] == "CHASIS":
        cursor.execute("""SELECT s.id, b.id FROM chasis_slot s
            JOIN activo b ON b.hostname=s.hostname_servidor AND b.tipo_activo='SERVIDOR'
            JOIN servidor v ON v.id=b.id AND v.tipo='BLADE'
            WHERE s.chasis_id=%s AND b.cluster=%s AND b.ubicacion=%s
            FOR UPDATE OF s, b""", (activo_id,activo.get("cluster"),activo["ubicacion"]))
        for slot_id,servidor_id in cursor.fetchall():
            cursor.execute("UPDATE servidor SET id_chasis_slot=%s WHERE id=%s AND id_chasis_slot IS NULL",
                (slot_id,servidor_id))
            if cursor.rowcount!=1:
                raise DatosIncompletos("El blade ya está asignado a otro slot.")
            cursor.execute("UPDATE chasis_slot SET servidor_id=%s WHERE id=%s",(servidor_id,slot_id))


def crear_servidor(conexion, ficha):
    return crear_activo(conexion, ficha)


def registrar_evento_estado(cursor_o_conexion, activo_id, campo, valor_nuevo, descripcion, fecha,
                            componente_tipo=None, componente_sn=None):
    """Inserta un evento en historico_estado dentro de la transacción del llamador."""
    datos = {"activo_id": activo_id, "componente_tipo": componente_tipo, "componente_sn": componente_sn,
             "campo": campo, "valor_nuevo": valor_nuevo, "descripcion": descripcion, "fecha_cambio": fecha}
    if hasattr(cursor_o_conexion, "cursor"):
        with cursor_o_conexion.cursor() as cursor:
            return _insertar(cursor, "historico_estado", datos)
    return _insertar(cursor_o_conexion, "historico_estado", datos)


def guardar_metricas(conexion, activo_id, metricas):
    with conexion.cursor() as cursor:
        cursor.executemany("""INSERT INTO metrica_historica
            (activo_id, componente_tipo, componente_serial, nombre_metrica, valor, fecha_medicion)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            [(activo_id, fila.get("componente_tipo"), fila.get("componente_serial"),
              fila["nombre_metrica"], fila["valor"], fila["fecha_medicion"]) for fila in metricas])
