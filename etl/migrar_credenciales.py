"""Convierte credenciales existentes dentro de una sola transacción; no ejecuta DDL."""
import argparse
import json

from etl.config import cargar_configuracion
from etl.credenciales import cifrar, descifrar
from etl.db import conexion_bd
from etl.errores import BaseNoDisponible


def convertir(config, *, verificar=False):
    if config.credential_key is None:
        raise BaseNoDisponible("Configura y respalda la llave externa antes de convertir credenciales.")
    revisadas = convertidas = 0
    with conexion_bd(config) as db, db.cursor() as cur:
        cur.execute("SELECT id,clave,clave_privacidad FROM monitoreo_snmp ORDER BY id FOR UPDATE")
        for identificador, clave, privacidad in cur.fetchall():
            revisadas += 1
            valores = []
            cambio = False
            for campo, valor in (("clave", clave), ("clave_privacidad", privacidad)):
                plano = descifrar(valor, config.credential_key, campo)
                pendiente = valor is not None and not valor.startswith("enc:v1:")
                cambio |= pendiente
                valores.append(cifrar(plano, config.credential_key, campo) if pendiente and not verificar else valor)
            if cambio:
                convertidas += 1
                if not verificar:
                    cur.execute("UPDATE monitoreo_snmp SET clave=%s,clave_privacidad=%s WHERE id=%s", (*valores, identificador))
    return {"conexiones_revisadas": revisadas, "pendientes" if verificar else "convertidas": convertidas}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", action="store_true", help="Solo comprueba descifrado y cuenta texto previo")
    args = parser.parse_args()
    try:
        print(json.dumps(convertir(cargar_configuracion(), verificar=args.verificar)))
    except BaseNoDisponible as error:
        print(json.dumps({"ok": False, "mensaje": str(error)}, ensure_ascii=True))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
