"""Perfil HPE ProLiant según MAPEO-SERVIDOR.md y las MIB locales.

Escalares con .0; columnas sin índices de instancia. Otros fabricantes se
incorporarán como perfiles independientes dentro de este módulo.
"""
OIDS_IDENTIDAD = {
    "sys_object_id": "1.3.6.1.2.1.1.2.0",
    "sys_name": "1.3.6.1.2.1.1.5.0",
    "ubicacion_snmp": "1.3.6.1.2.1.1.6.0",
    "hostname": "1.3.6.1.4.1.232.11.2.2.12.0",
    "numero_serie": "1.3.6.1.4.1.232.2.2.2.1.0",
    "modelo": "1.3.6.1.4.1.232.2.2.4.2.0",
    "estado_operativo": "1.3.6.1.4.1.232.6.1.3.0",
    "version_so": "1.3.6.1.4.1.232.11.2.2.2.0",
    "version_firmware": "1.3.6.1.4.1.232.1.2.6.1.0",
    "consumo_electrico_w": "1.3.6.1.4.1.232.6.2.15.3.0",
    "ram_total_mb": "1.3.6.1.4.1.232.11.2.13.1.0",
    "ram_libre_mb": "1.3.6.1.4.1.232.11.2.13.2.0",
}

def columnas(base, campos):
    return {campo: f"{base}.{columna}" for campo, columna in campos.items()}

OIDS_CPU = columnas("1.3.6.1.4.1.232.1.2.2.1.1", {
    "modelo": 3, "velocidad_mhz": 4, "estado": 6, "marca": 8,
    "revision_arquitectura": 14, "cantidad_nucleos": 15, "numero_serial": 16, "hilos_por_nucleo": 25,
})
OIDS_CACHE = columnas("1.3.6.1.4.1.232.1.2.2.3.1", {"nivel": 2, "capacidad_kb": 3})
OIDS_RAM = columnas("1.3.6.1.4.1.232.2.2.4.5.1", {
    "capacidad_kb": 3, "marca": 7, "modelo": 8, "numero_serial": 10,
    "estado": 11, "velocidad_mhz": 13,
})
OIDS_DISCOS_INTERNOS = columnas("1.3.6.1.4.1.232.3.2.5.1.1", {
    "modelo": 3, "estado": 37, "capacidad_mb": 45, "numero_serial": 51,
    "rotacion": 59, "tipo": 60,
})
OIDS_CONTROLADORA_RAID = columnas("1.3.6.1.4.1.232.3.2.2.1.1", {
    "modelo": 2, "estado": 6, "numero_serial": 15,
})
OIDS_UNIDADES_LOGICAS = columnas("1.3.6.1.4.1.232.3.2.3.1.1", {
    "controladora": 1, "raid": 3, "capacidad_mb": 9,
})
OIDS_TARJETAS_RED = columnas("1.3.6.1.4.1.232.18.2.3.1.1", {
    "mac_address": 4, "slot": 5, "numero_puerto": 10, "condicion": 12,
    "estado": 14, "errores_transmision": 18, "errores_recepcion": 19,
    "errores_alineamiento": 20, "errores_fcs": 21, "velocidad_bps": 33,
    "velocidad_mbps": 36, "trafico_entrada_bytes": 37,
    "trafico_salida_bytes": 38, "modelo": 39,
})
OIDS_VENTILADORES = columnas("1.3.6.1.4.1.232.6.2.6.7.1", {"estado": 9, "velocidad_rpm": 12})
OIDS_FUENTES = columnas("1.3.6.1.4.1.232.6.2.9.3.1", {
    "estado": 4, "consumo_w": 7, "modelo": 10, "numero_serial": 11,
})
OIDS_TEMPERATURA = columnas("1.3.6.1.4.1.232.6.2.6.8.1", {"ubicacion": 3, "celsius": 4})
OIDS_IP = {"direccion": "1.3.6.1.2.1.4.20.1.1"}
OIDS_USO_CPU = {"porcentaje": "1.3.6.1.4.1.232.11.2.3.1.1.2"}
TABLAS_HPE = {
    "cpu": OIDS_CPU, "cache": OIDS_CACHE, "ram": OIDS_RAM,
    "disco": OIDS_DISCOS_INTERNOS, "controladora_raid": OIDS_CONTROLADORA_RAID,
    "unidad_logica": OIDS_UNIDADES_LOGICAS, "tarjeta_red": OIDS_TARJETAS_RED,
    "ventilador": OIDS_VENTILADORES, "fuente_poder": OIDS_FUENTES,
    "temperatura": OIDS_TEMPERATURA, "ip": OIDS_IP, "uso_cpu": OIDS_USO_CPU,
}

# Enumeración transcrita de cpqDaCntlrModel (CPQIDA-MIB).
MODELOS_CONTROLADORA_HPE = {
    1: 'other',
    2: 'ida',
    3: 'idaExpansion',
    4: 'ida-2',
    5: 'smart',
    6: 'smart-2e',
    7: 'smart-2p',
    8: 'smart-2sl',
    9: 'smart-3100es',
    10: 'smart-3200',
    11: 'smart-2dh',
    12: 'smart-221',
    13: 'sa-4250es',
    14: 'sa-4200',
    15: 'sa-integrated',
    16: 'sa-431',
    17: 'sa-5300',
    18: 'raidLc2',
    19: 'sa-5i',
    20: 'sa-532',
    21: 'sa-5312',
    22: 'sa-641',
    23: 'sa-642',
    24: 'sa-6400',
    25: 'sa-6400em',
    26: 'sa-6i',
    27: 'sa-generic',
    29: 'sa-p600',
    30: 'sa-p400',
    31: 'sa-e200',
    32: 'sa-e200i',
    33: 'sa-p400i',
    34: 'sa-p800',
    35: 'sa-e500',
    36: 'sa-p700m',
    37: 'sa-p212',
    38: 'sa-p410',
    39: 'sa-p410i',
    40: 'sa-p411',
    41: 'sa-b110i',
    42: 'sa-p712m',
    43: 'sa-p711m',
    44: 'sa-p812',
    45: 'sw-1210m',
    46: 'sa-p220i',
    47: 'sa-p222',
    48: 'sa-p420',
    49: 'sa-p420i',
    50: 'sa-p421',
    51: 'sa-b320i',
    52: 'sa-p822',
    53: 'sa-p721m',
    54: 'sa-b120i',
    55: 'hps-1224',
    56: 'hps-1228',
    57: 'hps-1228m',
    58: 'sa-p822se',
    59: 'hps-1224e',
    60: 'hps-1228e',
    61: 'hps-1228em',
    62: 'sa-p230i',
    63: 'sa-p430i',
    64: 'sa-p430',
    65: 'sa-p431',
    66: 'sa-p731m',
    67: 'sa-p830i',
    68: 'sa-p830',
    69: 'sa-p831',
    70: 'sa-p530',
    71: 'sa-p531',
    72: 'sa-p244br',
    73: 'sa-p246br',
    74: 'sa-p440',
    75: 'sa-p440ar',
    76: 'sa-p441',
    77: 'sa-p741m',
    78: 'sa-p840',
    79: 'sa-p841',
    80: 'sh-h240ar',
    81: 'sh-h244br',
    82: 'sh-h240',
    83: 'sh-h241',
    84: 'sa-b140i',
    85: 'sh-generic',
    86: 'sa-p240nr',
    87: 'sh-h240nr',
    88: 'sa-p840ar',
    89: 'sa-p542d',
    90: 's100i',
    91: 'e208i-p',
    92: 'e208i-a',
    93: 'e208i-c',
    94: 'e208e-p',
    95: 'p204i-b',
    96: 'p204i-c',
    97: 'p408i-p',
    98: 'p408i-a',
    99: 'p408e-p',
    100: 'p408i-c',
    101: 'p408e-m',
    102: 'p416ie-m',
    103: 'p816i-a',
    104: 'p408i-sb',
}
