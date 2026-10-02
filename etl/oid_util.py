"""Lectura acotada de columnas SNMP y conversión de valores ASN.1."""
from etl.snmp_cliente import SesionSNMP

SYSTEM = {"objeto": "1.3.6.1.2.1.1.2.0", "hostname": "1.3.6.1.2.1.1.5.0",
          "ubicacion": "1.3.6.1.2.1.1.6.0"}

def texto(valor):
    if valor is None:
        return None
    value = valor.prettyPrint() if hasattr(valor, "prettyPrint") else str(valor)
    return value.strip() or None

def numero(valor):
    try:
        return int(valor) if valor is not None else None
    except (TypeError, ValueError):
        return None

def filas(datos, columnas):
    """Agrupa columnas por índice completo, incluidos índices de varios componentes."""
    resultado = {}
    for nombre, raiz in columnas.items():
        prefijo = raiz + "."
        for oid, valor in datos.items():
            if oid.startswith(prefijo):
                resultado.setdefault(oid[len(prefijo):], {})[nombre] = valor
    return [(indice, resultado[indice]) for indice in sorted(resultado, key=lambda x: tuple(map(int, x.split("."))))]

async def leer_perfil(conexion, *, escalares=(), subarboles=()):
    with SesionSNMP(conexion) as sesion:
        datos = await sesion.obtener(list(dict.fromkeys([*SYSTEM.values(), *escalares])))
        for raiz in subarboles:
            datos.update(await sesion.recorrer(raiz))
        return datos
