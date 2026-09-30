"""
Define, como constantes, los OID numéricos propios del switch ArubaOS-CX (identidad, puertos,
tráfico, temperatura, consumo, fuentes, ventiladores y uso de CPU/RAM del propio switch),
transcritos tal cual de mibs/ALL-Supported-MIBs/MAPEO-SWITCH.md. El bloque de CPU/RAM "prestado"
de MIB de servidor HPE que describe ese mismo documento no se repite acá: lo reutiliza
extraccion/switch.py directamente desde oids/servidor.py.

Contenido:
- OIDS_IDENTIDAD, OIDS_PUERTOS, OIDS_TRAFICO, OIDS_TEMPERATURA, OIDS_CONSUMO, OIDS_FUENTES,
  OIDS_VENTILADORES, OIDS_USO_CPU_RAM: diccionarios nombre_de_campo -> OID (string), cada uno con
  los OID de la sección correspondiente de MAPEO-SWITCH.md.

Dependencias: ninguna de este proyecto (solo constantes). Lo usa extraccion/switch.py.
"""
