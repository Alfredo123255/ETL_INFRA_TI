"""Extracción de arreglo FC y componentes del host HPE que lo administra."""
from etl.extraccion.servidor import extraer_servidor_hpe
from etl.oid_util import leer_perfil
from etl.errores import ErrorExtraccion

async def extraer_storage(conexion):
    datos = await extraer_servidor_hpe(conexion)
    propios = await leer_perfil(conexion, subarboles=(
        "1.3.6.1.4.1.232.8.2.2.1.1",
        "1.3.6.1.4.1.232.16.2.2.1.1",
        "1.3.6.1.4.1.232.16.2.3.1.1",
        "1.3.6.1.4.1.232.16.2.5.1.1",
        "1.3.6.1.4.1.232.16.2.7.1.1",
    ))
    datos.update(propios)
    # El bloque Nimble es prestado y opcional en un equipo real.
    try:
        nimble = await leer_perfil(conexion, escalares=[
            f"1.3.6.1.4.1.37447.1.3.{col}.0" for col in (2, 4, 6, 7, 8, 10, 12, 13, 14, 15)])
        datos.update(nimble)
    except ErrorExtraccion:
        pass
    return datos
