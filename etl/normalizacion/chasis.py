"""
Convierte el diccionario oid -> valor crudo de un chasis blade (extraccion/chasis.py) a la
estructura de la ficha de ChasisBlade del esquema, usando pandas, transcribiendo
mibs/hpe-real/MAPEO-CHASIS.md: identidad, chasisSlots con su EstadoSlotEnum, ventiladores,
fuentes de poder y puertos de red de los módulos de interconexión.

Funciones:
- normalizar_chasis(datos_crudos: dict) -> dict: aplica las conversiones y traducciones de estado
  (incluida normalizar_estado_slot de normalizacion/estados.py) y arma el diccionario con los
  campos de la ficha de ChasisBlade y su lista de chasisSlots.

Dependencias: normalizacion/estados.py, normalizacion/reglas.py, pandas.
"""
