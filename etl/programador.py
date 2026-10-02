"""Programador independiente de la API; frecuencia de cada conexión en segundos."""
import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from etl.config import cargar_configuracion
from etl.db import conexion_bd, obtener_conexion
from etl.monitoreo import ejecutar_iteracion

LOG = logging.getLogger(__name__)
TICK_SEGUNDOS = 2
LOCK_ID = 68342117


def conexiones_programadas(config, conexion_id=None):
    with conexion_bd(config) as db, db.cursor() as cur:
        cur.execute("""SELECT id, frecuencia_actualizacion, fecha_ultima_actualizacion
            FROM monitoreo_snmp WHERE activo_id IS NOT NULL
              AND estado_conexion IN ('Activo', 'Sin conexión')
              AND frecuencia_actualizacion > 0 AND (%s IS NULL OR id=%s)
            ORDER BY id""", (conexion_id, conexion_id))
        return cur.fetchall()


def _vencida(ultima, frecuencia, ahora):
    if ultima is None:
        return True
    if ultima.tzinfo is not None:
        ultima = ultima.astimezone(timezone.utc).replace(tzinfo=None)
    return ultima + timedelta(seconds=frecuencia) <= ahora


async def _ejecutar(config, ids):
    async def una(conexion_id):
        try:
            resultado = await ejecutar_iteracion(config, conexion_id)
            LOG.info("Iteración: %s", json.dumps(resultado, ensure_ascii=False))
        except Exception:
            # Algunos clientes incluyen credenciales en el texto de las excepciones.
            LOG.error("No se completó la iteración de la conexión %s", conexion_id)
    semaforo = asyncio.Semaphore(4)
    async def limitada(conexion_id):
        async with semaforo:
            await una(conexion_id)
    await asyncio.gather(*(limitada(i) for i in ids))


async def iniciar_programador(config, *, una_vez=False, conexion_id=None):
    """Ejecuta el ciclo continuamente; un lock PG impide dos programadores simultáneos."""
    if una_vez:
        ids = [fila[0] for fila in conexiones_programadas(config, conexion_id)]
        await _ejecutar(config, ids)
        return
    guardia = obtener_conexion(config)
    try:
        guardia.autocommit = True
        with guardia.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,))
            if not cur.fetchone()[0]:
                raise RuntimeError("Ya hay un programador ETL en ejecución.")
        intentos = {}
        while True:
            ahora = datetime.now(timezone.utc).replace(tzinfo=None)
            filas = conexiones_programadas(config, conexion_id)
            vigentes = {fila[0] for fila in filas}
            intentos = {i: fecha for i, fecha in intentos.items() if i in vigentes}
            vencidas = [i for i, frecuencia, ultima in filas
                        if _vencida(max(filter(None, (ultima, intentos.get(i))), default=None), frecuencia, ahora)]
            if vencidas:
                await _ejecutar(config, vencidas)
                intentos.update({i: datetime.now(timezone.utc).replace(tzinfo=None) for i in vencidas})
            await asyncio.sleep(TICK_SEGUNDOS)
    finally:
        guardia.close()


def main():
    parser = argparse.ArgumentParser(description="Monitorea activos vinculados por SNMPv3")
    parser.add_argument("--una-vez", action="store_true", help="Ejecuta una iteración y termina")
    parser.add_argument("--conexion-id", type=int, help="Limita la ejecución a esta conexión")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(iniciar_programador(cargar_configuracion(), una_vez=args.una_vez,
                                        conexion_id=args.conexion_id))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
