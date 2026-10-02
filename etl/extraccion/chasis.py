"""Extracción de chasis HPE c7000, sus slots y componentes."""
from etl.oid_util import leer_perfil

async def extraer_chasis(conexion):
    return await leer_perfil(conexion, subarboles=(
        "1.3.6.1.4.1.232.22.2.3",
        "1.3.6.1.4.1.232.22.2.4",
        "1.3.6.1.4.1.232.22.2.5",
        "1.3.6.1.4.1.232.22.2.6",
        "1.3.6.1.2.1.2.2.1",
        "1.3.6.1.2.1.31.1.1.1",
    ))
