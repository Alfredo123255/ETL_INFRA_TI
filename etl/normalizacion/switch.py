"""
Convierte el diccionario oid -> valor crudo de un switch (extraccion/switch.py) a la estructura
de la ficha de Switch del esquema, usando pandas, transcribiendo
mibs/ALL-Supported-MIBs/MAPEO-SWITCH.md: identidad, puertos físicos filtrados de los
virtuales/LAG, temperatura, consumo, fuentes, ventiladores, uso de CPU/RAM y el bloque de CPU/RAM
prestado de MIB de servidor HPE.

Funciones:
- normalizar_switch(datos_crudos: dict) -> dict: aplica las conversiones y las traducciones de
  estado propias de los enums de Aruba (distintos de los de HPE) y arma el diccionario con los
  campos de la ficha de Switch y su lista de puertos.

Dependencias: normalizacion/estados.py, normalizacion/reglas.py, pandas.
"""
