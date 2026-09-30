"""
Centraliza la traducción de los enums de estado propios de cada fabricante/MIB al EstadoEnum
único del esquema (Encendido, Apagado, Degradado) y al EstadoSlotEnum de los slots de blade del
chasis (Ocupado, Libre, Degradado), siguiendo las tablas de traducción documentadas en cada
MAPEO-*.md de mibs/. Cada MIB tiene su propio enum de origen; nunca se reutilizan los valores
numéricos de un fabricante para otro.

Funciones:
- normalizar_estado(valor_origen: int, tabla_traduccion: dict[int, str]) -> str: aplica la tabla
  de traducción de un objeto puntual (por ejemplo cpqHeFltTolPowerSupplyCondition) y devuelve uno
  de los tres valores de EstadoEnum.
- normalizar_estado_slot(presente: int, estado: int) -> str: combina presencia y condición de un
  slot de blade (cpqRackServerBladePresent + cpqRackServerBladeStatus) en un valor de
  EstadoSlotEnum, según la regla documentada en mibs/hpe-real/MAPEO-CHASIS.md sección 2.2.

Dependencias: ninguna de este proyecto. Lo usan todos los módulos de normalizacion/ por tipo de
activo.
"""
