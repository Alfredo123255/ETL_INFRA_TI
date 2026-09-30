"""
Define, como constantes, los OID numéricos propios del arreglo Fibre Channel (controladora RAID,
discos físicos, volúmenes lógicos, HBA del host, y los objetos prestados de NIMBLE-MIB y
FCMGMT-MIB), transcritos tal cual de mibs/hpe-real/MAPEO-STORAGE.md.

Contenido:
- OIDS_IDENTIDAD, OIDS_DISCOS, OIDS_CONTROLADORA_RAID, OIDS_TARJETA_FC, OIDS_NIMBLE_PRESTADO,
  OIDS_FCMGMT_PRESTADO: diccionarios nombre_de_campo -> OID (string), cada uno con los OID de la
  sección correspondiente de MAPEO-STORAGE.md; los dos últimos diccionarios están marcados como
  prestados y deben poder omitirse si el ETL corre contra un arreglo real.

Dependencias: ninguna de este proyecto (solo constantes). Lo usa extraccion/storage.py.
"""
