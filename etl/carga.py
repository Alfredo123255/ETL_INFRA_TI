"""Registro inicial atómico de ficha, componentes y mediciones en PostgreSQL."""
from datetime import datetime, timezone
import psycopg2
from etl.db import conexion_bd
from etl.errores import ActivoDuplicado, BaseNoDisponible, DatosIncompletos
from etl.metricas import construir_metricas
from etl.repositorio import crear_servidor, guardar_metricas


def cargar_registro(config, ficha, ubicacion=None):
    """Reutilizable desde API y ETL; no guarda credenciales ni programa monitoreo."""
    # Convención de la simulación: datacenter / rack / posición.
    datacenter = ubicacion or (ficha.get("ubicacion_snmp") or "").split("/", 1)[0].strip()
    if not datacenter:
        raise DatosIncompletos("Falta la ubicación del datacenter en SNMP o en la solicitud.")
    ficha = {**ficha, "activo": {**ficha["activo"], "ubicacion": datacenter}}
    # metrica_historica usa TIMESTAMP sin zona: se almacena UTC en todas las mediciones.
    metricas = construir_metricas("SERVIDOR", ficha, datetime.now(timezone.utc).replace(tzinfo=None))
    try:
        with conexion_bd(config) as conexion:
            activo_id, cantidades = crear_servidor(conexion, ficha)
            guardar_metricas(conexion, activo_id, metricas)
    except psycopg2.Error as exc:
        if exc.pgcode == "23505":
            raise ActivoDuplicado("Ya existe un activo con esa serie o hostname.") from None
        if exc.pgcode in ("23502", "23503", "23514", "22003", "22001", "22P02"):
            raise DatosIncompletos("Los datos del activo no cumplen las restricciones del esquema.") from None
        raise BaseNoDisponible("No se pudo completar el registro en PostgreSQL.") from None
    activo = ficha["activo"]
    return {"ok": True, "activo_id": activo_id, "numero_serie": activo["numero_serie"],
        "hostname": activo["hostname"], "fabricante": activo["fabricante"],
        "tipo_activo": "SERVIDOR", "modelo": activo["modelo"], "ubicacion": datacenter,
        "componentes": cantidades, "metricas_guardadas": len(metricas)}
