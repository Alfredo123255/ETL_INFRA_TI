"""SQL parametrizado de registro inicial; no administra el esquema."""
from etl.errores import DatosIncompletos

COLUMNAS = {
    "activo": ("numero_serie", "hostname", "fabricante", "modelo", "generacion", "ubicacion",
        "ip_gestion", "tipo_activo", "estado_operativo", "version_firmware",
        "ultima_actualizacion", "temperatura", "consumo_electrico_w"),
    "servidor": ("id", "ip_sistema_operativo", "version_so", "tipo"),
    "cpu": ("activo_id", "numero_serial", "familia", "marca", "modelo", "velocidad_ghz",
        "cantidad_nucleos", "cantidad_hilos", "cache_l1_mb", "cache_l2_mb", "cache_l3_mb", "estado"),
    "ram": ("activo_id", "numero_serial", "marca", "modelo", "generacion", "velocidad_mhz", "capacidad_gb", "estado"),
    "disco": ("activo_id", "numero_serial", "marca", "tipo", "capacidad_gb", "velocidad_rpm", "estado", "modelo"),
    "tarjeta_red": ("activo_id", "numero_serial", "marca", "modelo", "estado", "cantidad_puertos"),
    "puerto_tarjeta_red": ("tarjeta_red_id", "numero_puerto", "mac_address", "velocidad", "estado"),
    "fuente_poder": ("activo_id", "numero_serial", "modelo", "consumo_w", "tipo_corriente", "estado"),
    "ventilador": ("activo_id", "numero_serial", "velocidad_rpm", "modelo", "estado"),
    "controladora_raid": ("activo_id", "modelo", "raid", "numero_serial", "estado"),
}


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
    return cursor.fetchone()[0]


def crear_servidor(conexion, ficha):
    """Inserta activo, subtipo, componentes y puertos dentro de la transacción del llamador."""
    activo = ficha["activo"]
    with conexion.cursor() as cursor:
        cursor.execute("SELECT nombre FROM datacenters WHERE nombre = %s", (activo["ubicacion"],))
        if cursor.fetchone() is None:
            raise DatosIncompletos("La ubicación no corresponde a un datacenter registrado.")
        cursor.execute("INSERT INTO modelos (nombre_modelo) VALUES (%s) ON CONFLICT (nombre_modelo) DO NOTHING",
                       (activo["modelo"],))
        activo_id = _insertar(cursor, "activo", activo)
        _insertar(cursor, "servidor", {"id": activo_id, **ficha["servidor"]})
        cantidades = {}
        for tabla, filas in ficha["componentes"].items():
            if tabla not in ("cpu", "ram", "disco", "tarjeta_red", "fuente_poder", "ventilador", "controladora_raid"):
                raise DatosIncompletos("Tipo de componente incompatible con el esquema.")
            cantidades[tabla] = len(filas)
            for fila in filas:
                puertos = fila.get("puertos", []) if tabla == "tarjeta_red" else []
                datos = {campo: valor for campo, valor in fila.items() if campo != "puertos"}
                componente_id = _insertar(cursor, tabla, {**datos, "activo_id": activo_id})
                if tabla == "tarjeta_red":
                    cantidades["puerto_tarjeta_red"] = cantidades.get("puerto_tarjeta_red", 0) + len(puertos)
                    for puerto in puertos:
                        _insertar(cursor, "puerto_tarjeta_red", {**puerto, "tarjeta_red_id": componente_id})
        cantidades.setdefault("puerto_tarjeta_red", 0)
    return activo_id, cantidades


def guardar_metricas(conexion, activo_id, metricas):
    with conexion.cursor() as cursor:
        cursor.executemany("""INSERT INTO metrica_historica
            (activo_id, componente_tipo, componente_serial, nombre_metrica, valor, fecha_medicion)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            [(activo_id, fila.get("componente_tipo"), fila.get("componente_serial"),
              fila["nombre_metrica"], fila["valor"], fila["fecha_medicion"]) for fila in metricas])
