"""Extracción ArubaOS-CX con IF-MIB y MIB del equipo."""
from etl.oid_util import leer_perfil

async def extraer_switch(conexion):
    return await leer_perfil(conexion, subarboles=(
        "1.3.6.1.4.1.47196.4.1.1.3.11",
        "1.3.6.1.4.1.47196.4.1.1.3.22",
        "1.3.6.1.4.1.47196.4.1.1.3.26",
        "1.3.6.1.4.1.232.1.2.2.1.1",
        "1.3.6.1.4.1.232.1.2.2.3.1",
        "1.3.6.1.4.1.232.2.2.4.5.1",
        "1.3.6.1.2.1.2.2.1",
        "1.3.6.1.2.1.31.1.1.1",
    ))
