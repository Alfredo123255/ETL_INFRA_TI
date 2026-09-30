"""
Define, como constantes, los OID numéricos del chasis blade HPE BladeSystem c7000, transcritos
tal cual de mibs/hpe-real/MAPEO-CHASIS.md (identidad, chasisSlots, ventiladores, fuentes de poder
y puertos de red de los módulos de interconexión). Estas mismas constantes las reutiliza
extraccion/blade.py para los campos de ventiladores, fuentes y red que el blade no tiene propios.

Contenido:
- OIDS_IDENTIDAD, OIDS_SLOTS, OIDS_VENTILADORES, OIDS_FUENTES, OIDS_PUERTOS_RED: diccionarios
  nombre_de_campo -> OID (string), cada uno con los OID de la sección correspondiente de
  MAPEO-CHASIS.md.

Dependencias: ninguna de este proyecto (solo constantes). Lo usan extraccion/chasis.py y
extraccion/blade.py.
"""
