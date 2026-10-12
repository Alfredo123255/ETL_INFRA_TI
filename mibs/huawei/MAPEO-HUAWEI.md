# MIB Huawei y agentes simulados

Se movió íntegro el paquete recibido de `Downloads/MIBS-HUAWEI` a esta carpeta:
40 archivos en cinco familias. Los ZIP originales se conservan; el generador
[`data/generar_agentes_huawei.py`](../../data/generar_agentes_huawei.py) lee sus
MIB internos directamente y resuelve OID por nombre para producir los cuatro
`public.snmprec`. Los valores de hardware son de laboratorio, no inventarios
capturados de dispositivos reales.

| Agente | MIB principal | Enterprise | Tipo |
|---|---|---:|---|
| 2288H V5 rack | HUAWEI-SERVER-iBMC-MIB V502 | 2011 | SERVIDOR |
| CH121 V5 blade | HUAWEI-SERVER-iBMC-MIB V670 | 2011 | SERVIDOR |
| E9000/MM910 | OSCA-MIB V763 | 2011 | CHASIS |
| OceanStor Dorado 6.1.6 | ISM + HUAWEI-STORAGE-* | 34774 | STORAGE |

OID base representativos; las tablas llevan un índice al final, los escalares
terminan en `.0`:

| Dato | OID base |
|---|---|
| iBMC: serie del servidor/blade | `1.3.6.1.4.1.2011.2.235.1.1.1.7` |
| iBMC: tipo de RAM | `1.3.6.1.4.1.2011.2.235.1.1.16.50.1.11` |
| iBMC: AC/DC de fuente | `1.3.6.1.4.1.2011.2.235.1.1.6.50.1.3` |
| MM910: serie del chasis | `1.3.6.1.4.1.2011.2.82.1.82.2.2001.1.15` |
| MM910: serie blade en bahía 1 | `1.3.6.1.4.1.2011.2.82.1.82.4.1.2004.1.10` |
| Dorado: serie del arreglo | `1.3.6.1.4.1.34774.4.1.1.1` |
| Dorado: serie de disco | `1.3.6.1.4.1.34774.4.1.23.5.1.1.15` |
| Dorado: IOPS por nodo | `1.3.6.1.4.1.34774.4.1.21.3.1.5` |

El detector SNMP usa `sysObjectID` para el fabricante y exige un subárbol
propio antes de elegir servidor, chasis o storage. El perfil iBMC separa rack
de blade con `deviceslotID` y `shelfSerialNumber`. Los archivos de extracción
y normalización de servidor, chasis y storage contienen los perfiles Huawei
junto a los HPE; `etl/ciclo.py` los despacha al mismo registro y
monitoreo que HPE. La serie FRU de un blade en OSCA-MIB se cruza con el activo
blade del mismo datacenter para vincular la bahía.

El iBMC de la muestra no publica sistema operativo, serie de CPU/NIC ni
consumo individual de fuente; esos campos quedan nulos. OSCA-MIB da velocidad
de ventilador en porcentaje, así que RPM también queda nulo. El MIB de Dorado
sí aporta IOPS y latencia, que se guardan como métricas históricas.
No se recibió un MIB de switch Huawei, por lo que ese perfil sigue sin soporte.
