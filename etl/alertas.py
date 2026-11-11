"""Condiciones persistentes e historial; usa la transaccion del ciclo llamador."""
from datetime import datetime, timezone
from decimal import Decimal
from psycopg2.extras import RealDictCursor

from etl.db import conexion_bd
from etl.repositorio import registrar_evento_estado

COMPONENTES = ("cpu", "ram", "disco", "fuente_poder", "ventilador", "controladora_raid", "tarjeta_red", "puerto_switch", "chasis_slot")
NOMBRES = {"cpu_uso_ghz": "Uso de CPU", "ram_uso_gb": "Uso de memoria RAM", "disco_uso_gb": "Uso de disco", "almacenamiento_uso_tb": "Capacidad de almacenamiento usada", "equipo_temperatura_c": "Temperatura", "equipo_consumo_w": "Consumo eléctrico", "red_trafico_entrada_mbps": "Tráfico de entrada", "red_trafico_salida_mbps": "Tráfico de salida", "red_utilizacion_pct": "Utilización del enlace", "almacenamiento_iops": "IOPS", "almacenamiento_latencia_ms": "Latencia", "almacenamiento_throughput_lectura_mbps": "Throughput de lectura", "almacenamiento_throughput_escritura_mbps": "Throughput de escritura"}
PORCENTAJES = {"cpu_uso_ghz", "ram_uso_gb", "disco_uso_gb", "almacenamiento_uso_tb", "red_utilizacion_pct"}


def etiqueta_componente(tabla, fila, posicion):
    campo = "numero_slot" if tabla == "chasis_slot" else "numero_puerto" if tabla in ("puerto_switch", "puerto_tarjeta_red") else "numero_serial"
    valor = fila.get(campo)
    etiqueta = (str(valor) if campo == "numero_serial" else f"{campo}:{valor}") if valor is not None and str(valor).strip() else f"posicion:{posicion}"
    if tabla == "puerto_tarjeta_red":
        etiqueta = f"tarjeta:{fila['tarjeta_red_id']}/{etiqueta}"
    return etiqueta


def _evento(cur, activo, clave, valor, descripcion, fecha):
    tipo, serial, campo = clave
    cur.execute("""SELECT campo,valor_nuevo FROM historico_estado WHERE activo_id=%s AND campo IN (%s,%s)
        AND componente_tipo IS NOT DISTINCT FROM %s AND componente_sn IS NOT DISTINCT FROM %s
        ORDER BY fecha_cambio DESC,id DESC LIMIT 1""", (activo, campo, "cierre_alerta_" + campo, tipo, serial))
    anterior = cur.fetchone()
    if anterior is None or anterior["campo"] != campo or anterior["valor_nuevo"] != valor:
        registrar_evento_estado(cur, activo, campo, valor, descripcion, fecha, tipo, serial)


def cerrar_alertas_administrativamente(cur, activo_id, motivo, fecha):
    """Cierre idempotente; conserva causa, última lectura y fecha del activo."""
    descripcion = "Cerrada por baja del activo" if motivo == "baja" else "Cerrada por inicio de mantenimiento"
    valor = "Cerrada por baja" if motivo == "baja" else "Cerrada por mantenimiento"
    cur.execute("""UPDATE alerta SET fecha_resolucion=GREATEST(fecha_inicio,%s),
        descripcion=descripcion || E'\\n' || %s
        WHERE activo_id=%s AND fecha_resolucion IS NULL
        RETURNING id,campo,componente_tipo,componente_sn,descripcion,fecha_resolucion""",
        (fecha, descripcion, activo_id))
    cerradas = cur.fetchall()
    for alerta in cerradas:
        registrar_evento_estado(cur, activo_id, "cierre_alerta_" + alerta["campo"], valor,
            f"Alerta #{alerta['id']}. {alerta['descripcion']}", alerta["fecha_resolucion"],
            alerta["componente_tipo"], alerta["componente_sn"])
    return len(cerradas)


def evaluar_alertas(db, activo_id, *, fecha=None, lectura_snmp=False, fallo_snmp=False,
                    tablas_omitidas=(), hoy=None):
    """No interpreta ausencia de datos como recuperacion. No hace commit ni consulta SNMP."""
    fecha = fecha or datetime.now(timezone.utc).replace(tzinfo=None)
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        # Mismo orden de bloqueo que monitoreo, mantenimiento y baja.
        cur.execute("SELECT * FROM monitoreo_snmp WHERE activo_id=%s ORDER BY id FOR UPDATE", (activo_id,))
        conexiones = cur.fetchall()
        conexion = conexiones[-1] if conexiones else None
        cur.execute("SELECT * FROM activo WHERE id=%s FOR UPDATE", (activo_id,))
        activo = cur.fetchone()
        if not activo:
            return {"creadas": 0, "resueltas": 0, "actualizadas": 0}
        if activo["estado_operativo"] == "Baja" or activo["mantenimiento_activo"]:
            motivo = "baja" if activo["estado_operativo"] == "Baja" else "mantenimiento"
            campo, valor = ("estado_operativo", "Baja") if motivo == "baja" else ("mantenimiento_activo", "true")
            # Repara episodios anteriores usando el inicio administrativo registrado.
            cur.execute("""SELECT fecha_cambio FROM historico_estado WHERE activo_id=%s
                AND campo=%s AND valor_nuevo=%s ORDER BY fecha_cambio DESC,id DESC LIMIT 1""",
                (activo_id, campo, valor))
            inicio = cur.fetchone()
            cerradas = cerrar_alertas_administrativamente(cur, activo_id, motivo,
                inicio["fecha_cambio"] if inicio else fecha)
            return {"creadas": 0, "resueltas": 0, "actualizadas": 0, "cerradas_administrativamente": cerradas}
        cur.execute("""SELECT max(fecha_cambio) AS limite FROM historico_estado WHERE activo_id=%s
            AND ((campo='mantenimiento_activo' AND valor_nuevo='false')
                OR (campo LIKE 'cierre_alerta_%%' AND valor_nuevo='Cerrada por mantenimiento'))""", (activo_id,))
        fin_mantenimiento = cur.fetchone()["limite"]
        lectura_posterior = fin_mantenimiento is None or (activo["ultima_actualizacion"] is not None
            and activo["ultima_actualizacion"] > fin_mantenimiento)
        cur.execute("SELECT * FROM alerta WHERE activo_id=%s AND fecha_resolucion IS NULL FOR UPDATE", (activo_id,))
        abiertas = {(a["componente_tipo"], a["componente_sn"], a["campo"]): a for a in cur.fetchall()}
        condiciones = {}
        def poner(tipo, serial, campo, valor, severidad, descripcion, verificacion=fecha):
            condiciones[(tipo, serial, campo)] = (valor, severidad, descripcion, verificacion)

        if conexion and conexion["estado_conexion"] == "Sin conexión" and (fallo_snmp or (lectura_posterior and (None, None, "estado_conexion") not in abiertas)):
            poner(None, None, "estado_conexion", "Sin conexión", "Crítica", "Conexión SNMP: Sin conexión")
        elif conexion and conexion["estado_conexion"] == "Activo" and lectura_snmp:
            poner(None, None, "estado_conexion", "Activo", None, "Conexión SNMP restablecida")

        cur.execute("SELECT nombre,advertencia,critico FROM umbral")
        umbrales = {u["nombre"]: u for u in cur.fetchall()}
        eos = umbrales.get("dias_para_eos")
        if hoy is None:
            cur.execute("SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'America/Lima')::date AS hoy")
            hoy = cur.fetchone()["hoy"]
        if activo["fecha_eos"] is not None and eos and eos["advertencia"] is not None:
            dias = (activo["fecha_eos"] - hoy).days
            nivel = "Crítico" if dias < 0 else "Advertencia" if dias <= eos["advertencia"] else "Normal"
            poner(None, None, "umbral_dias_para_eos", nivel, "Crítica" if nivel == "Crítico" else "Media" if nivel == "Advertencia" else None,
                  f"EOS {'vencido' if dias < 0 else 'en ' + str(dias) + ' días'} ({activo['fecha_eos'].isoformat()})")
        elif (None, None, "umbral_dias_para_eos") in abiertas:
            poner(None, None, "umbral_dias_para_eos", "Sin configuración", None, "Evaluación de EOS retirada: sin fecha o sin días de aviso")
        # Retirar deliberadamente un umbral no equivale a una recuperacion fisica.
        for clave in abiertas:
            if clave[2].startswith("umbral_") and clave[2] != "umbral_dias_para_eos":
                u = umbrales.get(clave[2][7:])
                if u is None or u["advertencia"] is None or u["critico"] is None:
                    poner(*clave, "Sin umbral", None, "Umbral deshabilitado; condición retirada")

        vigente = conexion and conexion["estado_conexion"] == "Activo" and activo["ultima_actualizacion"] is not None
        if not fallo_snmp and lectura_posterior and (lectura_snmp or vigente):
            comprobacion = activo["ultima_actualizacion"] or fecha
            estado = activo["estado_operativo"]
            poner(None, None, "estado_operativo", estado, "Crítica" if estado in ("Apagado", "Degradado") else None,
                  f"Estado operativo: {estado}", comprobacion)
            identidades = set()
            for tabla in COMPONENTES:
                if tabla in tablas_omitidas:
                    continue
                relacion = "switch_id" if tabla == "puerto_switch" else "chasis_id" if tabla == "chasis_slot" else "activo_id"
                cur.execute(f"SELECT * FROM {tabla} WHERE {relacion}=%s ORDER BY id", (activo_id,))
                for pos, fila in enumerate(cur.fetchall()):
                    etiqueta = etiqueta_componente(tabla, fila, pos)
                    identidades.add((tabla, etiqueta))
                    estado = fila["estado"]
                    if estado and estado.casefold() == "degradado":
                        poner(tabla, etiqueta, "estado", estado, "Media", f"{tabla} ({etiqueta}): {estado}", comprobacion)
                    elif estado in ("Encendido", "OCUPADO", "LIBRE"):
                        poner(tabla, etiqueta, "estado", estado, None, f"{tabla} ({etiqueta}): {estado}", comprobacion)
            cur.execute("""SELECT p.* FROM puerto_tarjeta_red p JOIN tarjeta_red t ON t.id=p.tarjeta_red_id
                WHERE t.activo_id=%s ORDER BY p.tarjeta_red_id,p.id""", (activo_id,))
            posiciones = {}
            for fila in cur.fetchall():
                pos = posiciones.get(fila["tarjeta_red_id"], 0)
                posiciones[fila["tarjeta_red_id"]] = pos + 1
                etiqueta = etiqueta_componente("puerto_tarjeta_red", fila, pos)
                identidades.add(("puerto_tarjeta_red", etiqueta))
                if "puerto_tarjeta_red" not in tablas_omitidas and fila["estado"] in ("Encendido", "Degradado"):
                    poner("puerto_tarjeta_red", etiqueta, "estado", fila["estado"], "Media" if fila["estado"] == "Degradado" else None,
                          f"puerto_tarjeta_red ({etiqueta}): {fila['estado']}", comprobacion)

            # Solo un retiro registrado explicitamente permite cerrar una pieza ausente.
            for clave, alerta in abiertas.items():
                if clave[0] and clave[2] == "estado" and (clave[0], clave[1]) not in identidades:
                    cur.execute("""SELECT valor_nuevo,fecha_cambio FROM historico_estado WHERE activo_id=%s
                        AND componente_tipo=%s AND componente_sn=%s AND campo='presencia'
                        ORDER BY fecha_cambio DESC,id DESC LIMIT 1""", (activo_id, clave[0], clave[1]))
                    presencia = cur.fetchone()
                    if presencia and presencia["valor_nuevo"] == "Retirado" and presencia["fecha_cambio"] >= alerta["fecha_inicio"]:
                        poner(*clave, "Retirado", None, "Condición finalizada por retiro confirmado del componente", comprobacion)

            cur.execute("""SELECT
                (SELECT CASE WHEN bool_and(velocidad_ghz>0 AND cantidad_nucleos>0 AND velocidad_ghz IS NOT NULL AND cantidad_nucleos IS NOT NULL)
                    THEN sum(velocidad_ghz*cantidad_nucleos) END FROM cpu WHERE activo_id=%s) AS cpu_uso_ghz,
                (SELECT CASE WHEN bool_and(capacidad_gb>0 AND capacidad_gb IS NOT NULL) THEN sum(capacidad_gb) END FROM ram WHERE activo_id=%s) AS ram_uso_gb,
                (SELECT CASE WHEN bool_and(capacidad_gb>0 AND capacidad_gb IS NOT NULL) THEN sum(capacidad_gb) END FROM disco WHERE activo_id=%s) AS disco_uso_gb,
                (SELECT capacidad_total_tb FROM storage WHERE id=%s) AS almacenamiento_uso_tb""", (activo_id,)*4)
            capacidades = cur.fetchone()
            cur.execute("""SELECT DISTINCT ON (nombre_metrica,componente_tipo,componente_serial) * FROM metrica_historica
                WHERE activo_id=%s AND fecha_medicion=%s ORDER BY nombre_metrica,componente_tipo,componente_serial,id DESC""", (activo_id, activo["ultima_actualizacion"]))
            for m in cur.fetchall():
                nombre = m["nombre_metrica"]
                u = umbrales.get(nombre)
                if nombre == "red_ancho_banda_mbps" or not u or u["advertencia"] is None or u["critico"] is None or m["valor"] is None:
                    continue
                valor = m["valor"]
                if nombre in capacidades:
                    capacidad = capacidades[nombre]
                    if capacidad is None or capacidad <= 0:
                        continue
                    valor = Decimal(100) * valor / capacidad
                if activo["tipo_activo"] == "SWITCH" and m["componente_tipo"] == "puerto_switch":
                    cur.execute("SELECT estado FROM puerto_switch WHERE switch_id=%s AND numero_puerto=%s", (activo_id, m["componente_serial"]))
                    puerto = cur.fetchone()
                    if not puerto or puerto["estado"] != "Encendido":
                        continue
                nivel = "Crítico" if valor >= u["critico"] else "Advertencia" if valor >= u["advertencia"] else "Normal"
                limite = u["critico"] if nivel == "Crítico" else u["advertencia"]
                unidad = "%" if nombre in PORCENTAJES else "°C" if nombre == "equipo_temperatura_c" else "W" if nombre == "equipo_consumo_w" else "ms" if nombre.endswith("_ms") else "Mbps" if nombre.endswith("_mbps") else "IOPS"
                detalle = f"{NOMBRES.get(nombre, nombre)} en {valor:.2f} {unidad} ({'crítico' if nivel == 'Crítico' else 'advertencia'} desde {limite} {unidad})"
                if m["componente_serial"]:
                    detalle = f"{m['componente_serial']}: {detalle}"
                poner(m["componente_tipo"], m["componente_serial"], "umbral_" + nombre, nivel,
                      "Crítica" if nivel == "Crítico" else "Media" if nivel == "Advertencia" else None, detalle, m["fecha_medicion"])

        resultado = {"creadas": 0, "resueltas": 0, "actualizadas": 0}
        for clave, (valor, severidad, detalle, verificacion) in condiciones.items():
            anterior = abiertas.get(clave)
            if severidad is not None:
                if anterior is None:
                    cur.execute("""INSERT INTO alerta(activo_id,componente_tipo,componente_sn,campo,severidad,descripcion,fecha_inicio,ultima_verificacion)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", (activo_id, *clave, severidad, detalle, fecha, verificacion))
                    resultado["creadas"] += 1
                    _evento(cur, activo_id, clave, valor, detalle, fecha)
                else:
                    cur.execute("UPDATE alerta SET severidad=%s,descripcion=%s,ultima_verificacion=GREATEST(ultima_verificacion,%s) WHERE id=%s", (severidad, detalle, verificacion, anterior["id"]))
                    resultado["actualizadas"] += 1
                    if anterior["severidad"] != severidad:
                        _evento(cur, activo_id, clave, valor, detalle, fecha)
            elif anterior is not None:
                cur.execute("UPDATE alerta SET fecha_resolucion=%s,ultima_verificacion=GREATEST(ultima_verificacion,%s),descripcion=%s WHERE id=%s", (max(fecha, anterior["fecha_inicio"]), verificacion, detalle, anterior["id"]))
                resultado["resueltas"] += 1
                # El retiro ya tiene su evento presencia=Retirado.
                if valor != "Retirado":
                    _evento(cur, activo_id, clave, valor, "Condición recuperada o retirada. " + detalle, fecha)
        return resultado


def cerrar_alertas_tarjeta(cur, activo_id, tarjeta_id):
    """El evento de retiro de la NIC cubre sus puertos dependientes, sin duplicarlo."""
    fecha = datetime.now(timezone.utc).replace(tzinfo=None)
    cur.execute("""UPDATE alerta SET fecha_resolucion=GREATEST(fecha_inicio,%s),
        descripcion='Condición finalizada por retiro confirmado de la tarjeta de red'
        WHERE activo_id=%s AND componente_tipo='puerto_tarjeta_red' AND campo='estado'
          AND componente_sn LIKE %s AND fecha_resolucion IS NULL""",
        (fecha, activo_id, f"tarjeta:{tarjeta_id}/%"))


def revisar_alertas(config, ids=None):
    """Reevaluacion de calendario/configuracion. No escribe metricas ni fecha del activo."""
    with conexion_bd(config) as db, db.cursor() as cur:
        cur.execute("""SELECT a.id FROM activo a WHERE (%s IS NULL OR a.id=ANY(%s))
            AND ((a.estado_operativo<>'Baja' AND NOT a.mantenimiento_activo)
                OR EXISTS (SELECT 1 FROM alerta al WHERE al.activo_id=a.id AND al.fecha_resolucion IS NULL))
            ORDER BY a.id""", (ids, ids))
        activos = [r[0] for r in cur.fetchall()]
    for activo_id in activos:
        with conexion_bd(config) as db:
            evaluar_alertas(db, activo_id)
