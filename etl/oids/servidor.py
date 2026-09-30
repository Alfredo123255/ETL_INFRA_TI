"""
Define, como constantes, los OID numéricos de un servidor rack o blade HPE ProLiant, transcritos
tal cual de mibs/hpe-real/MAPEO-SERVIDOR.md (uno o varios diccionarios por grupo: identidad, CPU,
RAM, discos internos y controladora RAID, tarjetas de red Ethernet, ventiladores, fuentes de
poder, temperatura y consumo). Estas mismas constantes las reutilizan extraccion/blade.py,
extraccion/storage.py y extraccion/switch.py para los campos que, según sus respectivos
documentos de mapeo, se completan con objetos de servidor HPE.

Contenido:
- OIDS_IDENTIDAD, OIDS_CPU, OIDS_RAM, OIDS_DISCOS_INTERNOS, OIDS_CONTROLADORA_RAID,
  OIDS_TARJETAS_RED, OIDS_VENTILADORES, OIDS_FUENTES, OIDS_TEMPERATURA_CONSUMO: diccionarios
  nombre_de_campo -> OID (string), cada uno con los OID de la sección correspondiente de
  MAPEO-SERVIDOR.md.

Dependencias: ninguna de este proyecto (solo constantes). Lo usan extraccion/servidor.py,
extraccion/blade.py, extraccion/storage.py y extraccion/switch.py.
"""
