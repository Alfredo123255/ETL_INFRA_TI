"""Comprobación de compatibilidad de instalación; nunca crea ni altera objetos."""
import json

from etl.config import cargar_configuracion
from etl.db import conexion_bd
from etl.errores import BaseNoDisponible


REQUERIDAS = {
    ("monitoreo_snmp", "clave_privacidad"): "character varying",
    ("activo", "ultima_actualizacion"): "timestamp without time zone",
}


def verificar_columnas(conexion):
    with conexion.cursor() as cur:
        cur.execute("""SELECT table_name,column_name,data_type
            FROM information_schema.columns WHERE table_schema='public'
            AND ((table_name='monitoreo_snmp' AND column_name='clave_privacidad')
              OR (table_name='activo' AND column_name='ultima_actualizacion'))""")
        actuales = {(tabla, columna): tipo for tabla, columna, tipo in cur.fetchall()}
    pendientes = [f"{tabla}.{columna}: se requiere {tipo}"
                  for (tabla, columna), tipo in REQUERIDAS.items()
                  if actuales.get((tabla, columna)) != tipo]
    if pendientes:
        raise BaseNoDisponible("Esquema incompatible. " + "; ".join(pendientes)
            + ". Revisa schema.sql y las migraciones 001/002; no se aplican automáticamente.")
    return {"compatible": True, "columnas_verificadas": len(REQUERIDAS)}


def main():
    try:
        with conexion_bd(cargar_configuracion()) as db:
            resultado = verificar_columnas(db)
        print(json.dumps(resultado))
    except BaseNoDisponible as error:
        print(json.dumps({"compatible": False, "mensaje": str(error)}, ensure_ascii=True))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
