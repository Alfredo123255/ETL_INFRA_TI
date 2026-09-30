"""Extracción de servidores por fabricante, reutilizable desde API y ciclos ETL."""
from etl.detector import fabricante as reconocer_fabricante
from etl.errores import PerfilNoSoportado
from etl.oids.servidor import OIDS_IDENTIDAD, TABLAS_HPE
from etl.snmp_cliente import SesionSNMP

async def extraer_servidor_hpe(conexion):
    """Devuelve OID completo -> valor ASN.1 sin convertir unidades ni estados."""
    with SesionSNMP(conexion) as sesion:
        datos = await sesion.obtener(list(OIDS_IDENTIDAD.values()))
        objeto = datos.get(OIDS_IDENTIDAD["sys_object_id"])
        if objeto is None or reconocer_fabricante(str(objeto)) != "HPE":
            raise PerfilNoSoportado("El equipo no corresponde al perfil de servidor HPE.")
        for columnas in TABLAS_HPE.values():
            raiz = next(iter(columnas.values())).rsplit(".", 1)[0]
            valores = await sesion.recorrer(raiz)
            prefijos = tuple(oid + "." for oid in columnas.values())
            datos.update((oid, valor) for oid, valor in valores.items() if oid.startswith(prefijos))
        return datos

async def extraer_servidor(conexion, fabricante):
    extractores = {"HPE": extraer_servidor_hpe}
    extractor = extractores.get(fabricante)
    if extractor is None:
        raise PerfilNoSoportado("Fabricante de servidor sin perfil de extracción implementado.")
    return await extractor(conexion)
