"""Una iteración de monitoreo de un activo ya vinculado a una conexión SNMP."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pydantic import SecretStr
from psycopg2.extras import RealDictCursor

from etl.ciclo import preparar_registro_activo
from etl.db import conexion_bd
from etl.errores import DatosIncompletos, ErrorExtraccion
from etl.metricas import construir_metricas
from etl.repositorio import (COLUMNAS, _insertar, guardar_metricas, registrar_evento_estado,
    CAMPO_ESTADO_CONEXION, CAMPO_ESTADO_OPERATIVO)
from etl.snmp_cliente import ConexionSNMP
from api.dto import separar_destino
from api.seguridad import resolver_destino

SUBTIPOS = {"SERVIDOR": "servidor", "SWITCH": "switch", "STORAGE": "storage", "CHASIS": "chasis_blade"}
COMPATIBLES = {
    "SERVIDOR": ("cpu", "ram", "disco", "tarjeta_red", "fuente_poder", "ventilador", "controladora_raid"),
    "STORAGE": ("cpu", "ram", "disco", "tarjeta_red", "fuente_poder", "ventilador", "controladora_raid"),
    "SWITCH": ("puerto_switch", "cpu", "ram", "fuente_poder", "ventilador"),
    "CHASIS": ("chasis_slot", "tarjeta_red", "fuente_poder", "ventilador"),
}
RELACION = {"puerto_switch": "switch_id", "chasis_slot": "chasis_id", "puerto_tarjeta_red": "tarjeta_red_id"}
NUMERICOS_DOS_DECIMALES = {
    "activo": {"temperatura", "consumo_electrico_w"},
    "cpu": {"velocidad_ghz", "cache_l1_mb", "cache_l2_mb", "cache_l3_mb"},
    "ram": {"capacidad_gb"},
    "disco": {"capacidad_gb"},
    "fuente_poder": {"consumo_w"},
    "storage": {"capacidad_total_tb", "capacidad_usada_tb"},
}


@dataclass(frozen=True)
class ConexionMonitoreo:
    id: int
    activo_id: int
    ip_gestion: str
    usuario: str = field(repr=False)
    clave: SecretStr = field(repr=False)
    clave_privacidad: SecretStr | None = field(repr=False)


def leer_conexion(config, conexion_id):
    """Lee credenciales actuales en cada iteración; no las expone en logs/resultados."""
    with conexion_bd(config) as db, db.cursor() as cur:
        cur.execute("""SELECT activo_id, ip_gestion, usuario, clave, clave_privacidad
            FROM monitoreo_snmp WHERE id=%s AND activo_id IS NOT NULL
            AND estado_conexion IN ('Activo', 'Sin conexión')""", (conexion_id,))
        row = cur.fetchone()
    if not row:
        return None
    activo_id, ip, usuario, clave, privacidad = row
    if not ip or not usuario or not clave:
        raise DatosIncompletos("La conexión vinculada no tiene datos SNMP completos.")
    return ConexionMonitoreo(conexion_id, activo_id, ip, usuario, SecretStr(clave),
                            SecretStr(privacidad) if privacidad else None)


def _filas(cur, tabla, relacion, padre_id):
    cur.execute(f"SELECT * FROM {tabla} WHERE {relacion}=%s ORDER BY id FOR UPDATE", (padre_id,))
    return list(cur.fetchall())


def _identificador(tabla, fila, posicion):
    campo = "numero_slot" if tabla == "chasis_slot" else "numero_puerto" if tabla in ("puerto_switch", "puerto_tarjeta_red") else "numero_serial"
    valor = fila.get(campo)
    return (campo, str(valor)) if valor is not None and str(valor).strip() else ("posicion", posicion)


def _etiqueta(tabla, fila, posicion):
    tipo, valor = _identificador(tabla, fila, posicion)
    return f"{tipo}:{valor}" if tipo != "numero_serial" else valor


def _actualizar_fila(cur, tabla, fila_id, anterior, datos, *, forzar=()):
    permitidas = set(COLUMNAS[tabla]) - {"id", "activo_id", "switch_id", "chasis_id", "tarjeta_red_id"}
    preparados = {k: Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                   if v is not None and k in NUMERICOS_DOS_DECIMALES.get(tabla, ()) else v
                   for k, v in datos.items() if k in permitidas}
    cambios = {k: v for k, v in preparados.items() if anterior.get(k) != v}
    escritura = {**cambios, **{k: preparados[k] for k in forzar if k in preparados}}
    if escritura:
        columnas = list(escritura)
        cur.execute(f"UPDATE {tabla} SET {', '.join(k + '=%s' for k in columnas)} WHERE id=%s",
                    (*[escritura[k] for k in columnas], fila_id))
    return cambios


def _evento(cur, activo_id, tabla, etiqueta, estado, anterior, fecha):
    descripcion = (f"{tabla} {etiqueta}: {anterior or 'sin estado previo'} → {estado}")
    registrar_evento_estado(cur, activo_id, "estado", estado, descripcion, fecha, tabla, etiqueta)


def _reconciliar(cur, activo_id, tabla, padre_id, nuevas, fecha):
    relacion = RELACION.get(tabla, "activo_id")
    anteriores = _filas(cur, tabla, relacion, padre_id)
    disponibles = {fila["id"]: fila for fila in anteriores}
    eventos = cambios = 0
    for posicion, nueva in enumerate(nuevas):
        clave = _identificador(tabla, nueva, posicion)
        coincidencias = [(i, fila) for i, fila in disponibles.items()
                         if _identificador(tabla, fila, anteriores.index(fila)) == clave]
        if len(coincidencias) > 1:
            raise DatosIncompletos("Hay componentes duplicados en la base de datos.")
        puertos = nueva.get("puertos", []) if tabla == "tarjeta_red" else []
        datos = {k: v for k, v in nueva.items() if k != "puertos"}
        if coincidencias:
            id_fila, anterior = coincidencias[0]
            del disponibles[id_fila]
            modificados = _actualizar_fila(cur, tabla, id_fila, anterior, datos)
            cambios += bool(modificados)
            if "estado" in modificados:
                _evento(cur, activo_id, tabla, _etiqueta(tabla, nueva, posicion),
                        nueva["estado"], anterior.get("estado"), fecha)
                eventos += 1
        else:
            id_fila = _insertar(cur, tabla, {**datos, relacion: padre_id})
            cambios += 1
            if datos.get("estado") is not None:
                _evento(cur, activo_id, tabla, _etiqueta(tabla, nueva, posicion), datos["estado"], None, fecha)
                eventos += 1
        if tabla == "tarjeta_red":
            c, e = _reconciliar(cur, activo_id, "puerto_tarjeta_red", id_fila, puertos, fecha)
            cambios += c
            eventos += e
    for anterior in disponibles.values():
        if tabla == "tarjeta_red":
            c, e = _reconciliar(cur, activo_id, "puerto_tarjeta_red", anterior["id"], [], fecha)
            cambios += c
            eventos += e
        baja = "LIBRE" if tabla == "chasis_slot" else "Baja"
        datos_baja = {"estado": baja, **({"hostname_servidor": None} if tabla == "chasis_slot" else {})}
        if any(anterior.get(k) != v for k, v in datos_baja.items()):
            _actualizar_fila(cur, tabla, anterior["id"], anterior, datos_baja)
            posicion = anteriores.index(anterior)
            if anterior.get("estado") != baja:
                _evento(cur, activo_id, tabla, _etiqueta(tabla, anterior, posicion), baja,
                        anterior.get("estado"), fecha)
                eventos += 1
            cambios += 1
    return cambios, eventos


def _sincronizar_slots(cur, chasis_id):
    """Mantiene el vínculo blade/slot cuando SNMP cambia la ocupación del chasis."""
    cur.execute("""SELECT s.id, s.servidor_id, s.hostname_servidor, s.estado,
        a.cluster, a.ubicacion FROM chasis_slot s JOIN activo a ON a.id=s.chasis_id
        WHERE s.chasis_id=%s ORDER BY s.id FOR UPDATE OF s""", (chasis_id,))
    slots = cur.fetchall()
    deseados = {}
    for slot in slots:
        servidor = None
        if slot["estado"] != "LIBRE" and slot["hostname_servidor"]:
            cur.execute("""SELECT b.id FROM activo b JOIN servidor v ON v.id=b.id AND v.tipo='BLADE'
                WHERE b.hostname=%s AND b.cluster=%s AND b.ubicacion=%s""",
                (slot["hostname_servidor"], slot["cluster"], slot["ubicacion"]))
            coincidencias = cur.fetchall()
            if len(coincidencias) > 1:
                raise DatosIncompletos("El slot coincide con varios servidores blade.")
            servidor = coincidencias[0]["id"] if coincidencias else None
        deseados[slot["id"]] = servidor
    for slot in slots:
        anterior, nuevo = slot["servidor_id"], deseados[slot["id"]]
        if anterior is not None and anterior != nuevo:
            cur.execute("UPDATE servidor SET id_chasis_slot=NULL WHERE id=%s AND id_chasis_slot=%s",
                        (anterior, slot["id"]))
            cur.execute("UPDATE chasis_slot SET servidor_id=NULL WHERE id=%s", (slot["id"],))
    for slot in slots:
        nuevo = deseados[slot["id"]]
        if nuevo is not None and nuevo != slot["servidor_id"]:
            cur.execute("SELECT id_chasis_slot FROM servidor WHERE id=%s FOR UPDATE", (nuevo,))
            asignado = cur.fetchone()["id_chasis_slot"]
            if asignado is not None and asignado != slot["id"]:
                raise DatosIncompletos("El blade ya está asignado a otro slot.")
            cur.execute("UPDATE servidor SET id_chasis_slot=%s WHERE id=%s", (slot["id"], nuevo))
            cur.execute("UPDATE chasis_slot SET servidor_id=%s WHERE id=%s", (nuevo, slot["id"]))


def _bloquear_conexion(cur, referencia):
    cur.execute("""SELECT activo_id, ip_gestion, usuario, clave, clave_privacidad, estado_conexion
        FROM monitoreo_snmp WHERE id=%s FOR UPDATE""", (referencia.id,))
    row = cur.fetchone()
    if not row or row["activo_id"] != referencia.activo_id or row["ip_gestion"] != referencia.ip_gestion or \
       row["usuario"] != referencia.usuario or row["clave"] != referencia.clave.get_secret_value() or \
       row["clave_privacidad"] != (referencia.clave_privacidad.get_secret_value() if referencia.clave_privacidad else None):
        raise DatosIncompletos("La conexión cambió durante la consulta; se repetirá en el siguiente ciclo.")
    return row


def registrar_fallo(config, referencia, tipo):
    fecha = datetime.now(timezone.utc).replace(tzinfo=None)
    with conexion_bd(config) as db, db.cursor(cursor_factory=RealDictCursor) as cur:
        actual = _bloquear_conexion(cur, referencia)
        if actual["estado_conexion"] == "Activo":
            cur.execute("UPDATE monitoreo_snmp SET estado_conexion='Sin conexión' WHERE id=%s",
                        (referencia.id,))
            registrar_evento_estado(cur, referencia.activo_id, CAMPO_ESTADO_CONEXION,
                "Sin conexión", f"Falló la consulta SNMP ({tipo})", fecha)
            return {"conexion_id": referencia.id, "ok": False, "eventos": 1}
    return {"conexion_id": referencia.id, "ok": False, "eventos": 0}


def guardar_iteracion(config, referencia, ficha):
    """Compara y escribe activo, subtipo, componentes, eventos y métricas en una transacción."""
    fecha = datetime.now(timezone.utc).replace(tzinfo=None)
    activo = ficha["activo"]
    subtipo = SUBTIPOS.get(activo.get("tipo_activo"))
    if subtipo is None or subtipo not in ficha:
        raise DatosIncompletos("El tipo de activo consultado no es compatible.")
    metricas = construir_metricas(activo["tipo_activo"], ficha, fecha)
    with conexion_bd(config) as db, db.cursor(cursor_factory=RealDictCursor) as cur:
        conexion = _bloquear_conexion(cur, referencia)
        if conexion["estado_conexion"] == "Inactivo":
            return {"conexion_id": referencia.id, "omitida": True}
        cur.execute("SELECT * FROM activo WHERE id=%s FOR UPDATE", (referencia.activo_id,))
        anterior = cur.fetchone()
        if not anterior or anterior["tipo_activo"] != activo["tipo_activo"] or anterior["numero_serie"] != activo["numero_serie"]:
            raise DatosIncompletos("La identidad SNMP no coincide con el activo registrado.")
        # Los campos administrativos, ubicación y clúster pertenecen al front.
        campos_activo = {k: v for k, v in activo.items() if k in COLUMNAS["activo"] and
                         k not in ("numero_serie", "ubicacion", "cluster", "ip_gestion") and v is not None}
        campos_activo["ultima_actualizacion"] = activo["ultima_actualizacion"]
        cambios = bool(_actualizar_fila(cur, "activo", referencia.activo_id, anterior,
                                       campos_activo, forzar=("ultima_actualizacion",)))
        eventos = 0
        if anterior["estado_operativo"] != activo["estado_operativo"]:
            registrar_evento_estado(cur, referencia.activo_id, CAMPO_ESTADO_OPERATIVO,
                activo["estado_operativo"],
                f"Estado operativo: {anterior['estado_operativo']} → {activo['estado_operativo']}", fecha)
            eventos += 1
        cur.execute(f"SELECT * FROM {subtipo} WHERE id=%s FOR UPDATE", (referencia.activo_id,))
        anterior_subtipo = cur.fetchone()
        if anterior_subtipo is None:
            raise DatosIncompletos("Falta el subtipo del activo registrado.")
        # Un NULL en la extracción no borra metadatos completados desde el front.
        datos_subtipo = {k: v for k, v in ficha[subtipo].items() if v is not None}
        cambios += bool(_actualizar_fila(cur, subtipo, referencia.activo_id, anterior_subtipo, datos_subtipo))
        componentes = ficha.get("componentes", {})
        if set(componentes) - set(COMPATIBLES[activo["tipo_activo"]]):
            raise DatosIncompletos("La ficha contiene componentes incompatibles.")
        for tabla, filas in componentes.items():
            c, e = _reconciliar(cur, referencia.activo_id, tabla, referencia.activo_id, filas, fecha)
            cambios += c
            eventos += e
        if activo["tipo_activo"] == "CHASIS" and "chasis_slot" in componentes:
            _sincronizar_slots(cur, referencia.activo_id)
        guardar_metricas(db, referencia.activo_id, metricas)
        cur.execute("""UPDATE monitoreo_snmp SET estado_conexion='Activo',
            fecha_ultima_actualizacion=%s WHERE id=%s""", (fecha, referencia.id))
        if conexion["estado_conexion"] != "Activo":
            registrar_evento_estado(cur, referencia.activo_id, CAMPO_ESTADO_CONEXION,
                "Activo", "Conexión SNMP restablecida", fecha)
            eventos += 1
    return {"conexion_id": referencia.id, "activo_id": referencia.activo_id, "ok": True,
            "cambios": cambios, "eventos": eventos, "metricas": len(metricas)}


async def ejecutar_iteracion(config, conexion_id):
    referencia = leer_conexion(config, conexion_id)
    if referencia is None:
        return {"conexion_id": conexion_id, "omitida": True}
    try:
        host, puerto = separar_destino(referencia.ip_gestion)
        host = await resolver_destino(host, puerto, config.redes_permitidas, config.snmp_timeout)
        snmp = ConexionSNMP(host, puerto, referencia.usuario, referencia.clave, referencia.clave_privacidad,
                            config.snmp_context_name, config.snmp_timeout, config.snmp_retries)
        ficha = await preparar_registro_activo(snmp, config, ip_gestion=referencia.ip_gestion)
    except ErrorExtraccion as exc:
        return registrar_fallo(config, referencia, exc.tipo)
    except OSError:
        return registrar_fallo(config, referencia, "destino_no_disponible")
    return guardar_iteracion(config, referencia, ficha)
