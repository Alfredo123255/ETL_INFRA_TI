"""Contrato de nombres y unidades de las métricas históricas."""
from decimal import Decimal
from etl.errores import DatosIncompletos

NOMBRES_METRICAS = frozenset((
    "cpu_uso_ghz", "ram_uso_gb", "disco_uso_gb", "equipo_temperatura_c",
    "equipo_consumo_w", "red_trafico_entrada_mbps", "red_trafico_salida_mbps",
    "almacenamiento_uso_tb", "almacenamiento_iops", "red_ancho_banda_mbps",
    "almacenamiento_latencia_ms", "almacenamiento_throughput_lectura_mbps",
    "almacenamiento_throughput_escritura_mbps", "red_utilizacion_pct",
))
ALIAS = {"temperatura": "equipo_temperatura_c", "consumo_electrico_w": "equipo_consumo_w",
         "iops": "almacenamiento_iops", "latencia_ms": "almacenamiento_latencia_ms",
         "capacidad_usada_tb": "almacenamiento_uso_tb"}


def _decimal(valor):
    valor = Decimal(str(valor))
    if not valor.is_finite():
        raise DatosIncompletos("Una métrica contiene un valor no válido.")
    return valor


def _capacidad(ficha, recurso):
    piezas = ficha.get("componentes", {}).get(recurso, [])
    campos = ("velocidad_ghz", "cantidad_nucleos") if recurso == "cpu" else ("capacidad_gb",)
    if not piezas or any(p.get(c) is None or _decimal(p[c]) <= 0 for p in piezas for c in campos):
        return None
    return sum((_decimal(p[campos[0]]) * (_decimal(p[campos[1]]) if recurso == "cpu" else 1)
                for p in piezas), Decimal(0))


def construir_metricas(tipo_activo, datos_normalizados, marca_tiempo):
    mediciones = list(datos_normalizados.get("mediciones", []))
    if tipo_activo == "STORAGE":
        capacidad = datos_normalizados.get("storage", {})
        total, usada = capacidad.get("capacidad_total_tb"), capacidad.get("capacidad_usada_tb")
        total = _decimal(total) if total is not None else None
        usada = _decimal(usada) if usada is not None else None
        if (total is not None and total < 0) or (usada is not None and usada < 0) or (
                total is not None and usada is not None and usada > total):
            raise DatosIncompletos("La capacidad de almacenamiento no es válida.")
        if usada is not None:
            mediciones.append({"nombre_metrica": "almacenamiento_uso_tb", "valor": usada})
    resultado, claves = [], set()
    for medicion in mediciones:
        nombre = medicion["nombre_metrica"]
        valor = _decimal(medicion["valor"])
        if nombre in ("cpu_uso_pct", "ram_uso_pct"):
            recurso = nombre.split("_")[0]
            capacidad = _capacidad(datos_normalizados, recurso)
            if capacidad is None or not 0 <= valor <= 100:
                continue
            nombre = "cpu_uso_ghz" if recurso == "cpu" else "ram_uso_gb"
            valor = capacidad * valor / 100
        nombre = ALIAS.get(nombre, nombre)
        if nombre not in NOMBRES_METRICAS:
            raise DatosIncompletos("El nombre de la métrica no pertenece al catálogo.")
        clave = (nombre, medicion.get("componente_tipo"), medicion.get("componente_serial"))
        if clave in claves:
            raise DatosIncompletos("La lectura contiene una métrica duplicada.")
        claves.add(clave)
        resultado.append({**medicion, "nombre_metrica": nombre, "valor": valor,
                          "fecha_medicion": marca_tiempo})
    return resultado
