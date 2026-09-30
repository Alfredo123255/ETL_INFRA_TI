"""Construye filas de métricas sin incluirlas como columnas de la ficha."""
from decimal import Decimal
from etl.errores import DatosIncompletos


def construir_metricas(tipo_activo, datos_normalizados, marca_tiempo):
    resultado = []
    for medicion in datos_normalizados.get("mediciones", []):
        valor = Decimal(str(medicion["valor"]))
        if not valor.is_finite():
            raise DatosIncompletos("Una métrica contiene un valor no válido.")
        resultado.append({**medicion, "valor": valor, "fecha_medicion": marca_tiempo})
    return resultado
