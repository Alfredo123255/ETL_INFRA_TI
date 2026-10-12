"""Metadatos que se pueden deducir sin confundirlos con lecturas SNMP directas.

Los números de parte del catálogo corresponden a las capturas de prueba. Otros
modelos quedan sin clasificar hasta disponer de una ficha técnica verificable.
"""
import re


# Números de parte presentes en data/*/public.snmprec. Son DDR4 según las
# fichas de Samsung, Micron y las listas de compatibilidad del fabricante.
MODELOS_DDR4 = {
    "H5AN4G8NMFR", "HMA42GR7MFR4N", "HMA82GR7CJR8N", "HMA84GR7CJR4N",
    "M393A2G40DB0", "M393A2K40BB1", "M393A2K40DB3", "M393A4K40DB3",
    "MTA18ASF2G72PDZ",
}

# Números de parte leídos de cpqHeFltTolPowerSupplySparePartNum. La entrada
# AC de cada kit está documentada en las fichas de producto de HPE.
FUENTES_HPE_AC = {"720478-B21", "865408-B21", "865414-B21"}


def familia_cpu(modelo):
    if not modelo:
        return None
    valor = str(modelo)
    xeon = re.search(r"\bXeon(?:\(R\))?\s*(?:CPU\s*)?(Platinum|Gold|Silver|Bronze|E[357])\b", valor, re.I)
    if xeon:
        return "Xeon " + xeon.group(1).upper() if xeon.group(1).upper().startswith("E") else \
            "Xeon " + xeon.group(1).title()
    if re.search(r"\bEPYC\b", valor, re.I):
        return "EPYC"
    if re.search(r"\bRyzen\b", valor, re.I):
        return "Ryzen"
    if re.search(r"\bMIPS64\b", valor, re.I):
        return "MIPS64"
    return None


def generacion_ram(modelo):
    if not modelo:
        return None
    valor = str(modelo).upper()
    explicita = re.search(r"\bDDR[- ]?([345])\b|\bPC([345])[- ]", valor)
    if explicita:
        return "DDR" + (explicita.group(1) or explicita.group(2))
    numero_parte = valor.split("-", 1)[0]
    return "DDR4" if numero_parte in MODELOS_DDR4 else None


def corriente_desde_voltaje(descripcion):
    """Reconoce únicamente AC o DC explícitos en hpicfPsVoltageInfo."""
    if not descripcion:
        return None
    tipos = set(re.findall(r"\b(?:AC|DC)\b", str(descripcion).upper()))
    return next(iter(tipos)) if len(tipos) == 1 else None


def corriente_fuente_hpe(modelo, numero_parte):
    """Clasifica la entrada eléctrica solo con un modelo explícito o parte verificada."""
    tipos = set(re.findall(r"\b(?:AC|DC)\b", str(modelo or "").upper()))
    explicito = next(iter(tipos)) if len(tipos) == 1 else None
    por_parte = "AC" if str(numero_parte or "").strip().upper() in FUENTES_HPE_AC else None
    if len(tipos) > 1 or (explicito and por_parte and explicito != por_parte):
        return None
    return explicito or por_parte


def potencia_nominal_modelo(modelo):
    """Extrae los vatios rotulados en el modelo de una fuente, si aparecen."""
    if not modelo:
        return None
    coincidencia = re.search(r"(?<!\d)(\d{2,5})\s*W\b", str(modelo), re.I)
    return int(coincidencia.group(1)) if coincidencia else None
