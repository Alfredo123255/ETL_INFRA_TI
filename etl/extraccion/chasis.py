"""Extracción de chasis HPE c7000, sus slots y componentes."""
from etl.oid_util import leer_perfil
from etl.errores import PerfilNoSoportado

async def extraer_chasis_hpe(conexion):
    return await leer_perfil(conexion, subarboles=(
        "1.3.6.1.4.1.232.22.2.3",
        "1.3.6.1.4.1.232.22.2.4",
        "1.3.6.1.4.1.232.22.2.5",
        "1.3.6.1.4.1.232.22.2.6",
        "1.3.6.1.2.1.2.2.1",
        "1.3.6.1.2.1.31.1.1.1",
    ))


async def extraer_chasis_huawei(conexion):
    return await leer_perfil(conexion, escalares=("1.3.6.1.2.1.1.1.0",), subarboles=(
        "1.3.6.1.4.1.2011.2.82.1.82", "1.3.6.1.2.1.2.2.1",
        "1.3.6.1.2.1.31.1.1.1"))


async def extraer_chasis(conexion, fabricante="HPE"):
    perfiles = {"HPE": extraer_chasis_hpe, "Huawei": extraer_chasis_huawei}
    if fabricante not in perfiles:
        raise PerfilNoSoportado("Fabricante de chasis sin extractor implementado.")
    return await perfiles[fabricante](conexion)
