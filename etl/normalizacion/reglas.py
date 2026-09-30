"""Conversión de unidades compartida por los normalizadores."""
from decimal import Decimal

def dividir(valor, divisor):
    if valor is None or Decimal(str(valor)) < 0:
        return None
    return Decimal(str(valor)) / Decimal(divisor)

def mb_a_gb(valor_mb):
    return dividir(valor_mb, 1024)

def kb_a_gb(valor_kb):
    return dividir(valor_kb, 1024 ** 2)

def mhz_a_ghz(valor_mhz):
    return dividir(valor_mhz, 1000)

def calcular_hilos(nucleos, hilos_por_nucleo):
    if nucleos is None or hilos_por_nucleo is None or nucleos < 0 or hilos_por_nucleo < 0:
        return None
    return nucleos * hilos_por_nucleo
