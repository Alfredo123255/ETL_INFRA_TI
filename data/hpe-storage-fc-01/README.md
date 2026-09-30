# Agente simulado: hpe-storage-fc-01 (HPE ProLiant DL380 Gen9 + HPE StorageWorks MSA1000 FC)

Agente SNMP simulado con [snmpsim](https://pypi.org/project/snmpsim/) que responde **a la vez**
los módulos de servidor y los del arreglo Fibre Channel conectado, porque en la realidad
`cpqfca`/`cpqstsys` los implementa el mismo agente Insight Manager instalado en el servidor host
(ver [`MAPEO-STORAGE.md`](../../mibs/hpe-real/MAPEO-STORAGE.md) para el detalle de qué OID
corresponde a cada campo). El archivo de datos es [`public.snmprec`](./public.snmprec).

Las secciones **IOPS/latencia/capacidad_usada** y **tráfico de puerto Fibre Channel** de la
ficha se completan con objetos **prestados** de `mibs/prestados/` (`NIMBLE-MIB` y `FCMGMT-MIB`,
descargados de `github.com/librenms/librenms`): ni un servidor HPE ni un arreglo MSA/EVA reales
exponen esos OID bajo `cpqfca`/`cpqstsys`. Están marcados con bloques de comentario `#` en
`public.snmprec` y documentados en detalle en `MAPEO-STORAGE.md` (secciones 9 y 10). El ETL debe
poder ignorar esos bloques al consultar un servidor+arreglo HPE real.

## Cómo levantarlo

Requiere `snmpsim` + `pysnmp>=6.2.0,<7.0.0` instalados (`pip install snmpsim "pysnmp>=6.2.0,<7.0.0"`).

Se usa el mismo wrapper [`data/run_responder.py`](../run_responder.py) que el resto de agentes
de este repositorio.

Desde la raíz del repositorio:

```bash
python data/run_responder.py \
  --v3-engine-id=800000000153543031 \
  --v3-user=monitor_storagefc01 \
  --v3-auth-key='RcVQ87sKGKNAXteaPhvF' --v3-auth-proto=SHA \
  --v3-priv-key='87KIBACIxZCukpKjai0Z' --v3-priv-proto=AES \
  --agent-udpv4-endpoint=127.0.0.30:16700 \
  --data-dir="<ruta-absoluta-al-repo>\data\hpe-storage-fc-01" \
  --cache-dir="<ruta-absoluta-al-repo>\logs\snmpsim-cache"
```

`--data-dir` y `--cache-dir` deben ser **rutas absolutas**. También se puede levantar junto con
el resto de agentes vía [`data/start_agents.bat`](../start_agents.bat).

## Puerto y transporte

| | |
|---|---|
| Host | `127.0.0.30` (loopback; Windows trata todo `127.0.0.0/8` como loopback, así que cada agente puede usar una IP distinta sin configuración adicional — ver `data/verify_agents.py` para la lista completa) |
| Puerto UDP | **16700** |
| Verificado libre con | `netstat -ano \| findstr :16700` antes de asignarlo |

## Credenciales SNMPv3

| Parámetro | Valor |
|---|---|
| Usuario (`securityName`) | `monitor_storagefc01` |
| Nivel de seguridad | `authPriv` |
| Protocolo de autenticación | `SHA` (usmHMACSHAAuthProtocol) |
| Clave de autenticación | `RcVQ87sKGKNAXteaPhvF` |
| Protocolo de privacidad | `AES` (usmAesCfb128Protocol) |
| Clave de privacidad | `87KIBACIxZCukpKjai0Z` |
| Engine ID (`--v3-engine-id`) | `800000000153543031` (fijo; `53543031` = hex de "ST01") |
| **Contexto SNMPv3** | `public` |

⚠️ **El contexto importa.** Un cliente sin `contextName="public"` explícito ve su solicitud
descartada en silencio. Ver [`data/verify_agents.py`](../verify_agents.py).

Estas claves son solo para este entorno de prueba local (no usar en producción).

## Verificación rápida

```bash
python data/verify_agents.py
```

O con `snmpget` (net-snmp):

```bash
snmpget -v3 -u monitor_storagefc01 -l authPriv \
  -a SHA -A 'RcVQ87sKGKNAXteaPhvF' \
  -x AES -X '87KIBACIxZCukpKjai0Z' \
  -n public \
  127.0.0.30:16700 1.3.6.1.2.1.1.1.0
```

## Especificaciones simuladas (resumen)

- Servidor: ProLiant DL380 Gen9 · Serie `CZ2512090W` · `sysObjectID =
  1.3.6.1.4.1.232.9.4.14` (siguiendo el patrón numérico de los demás agentes de servidor) ·
  Ubicación `DataCenter-1 / Rack B03 / U10-11`
- Arreglo: **HPE StorageWorks MSA1000** (Fibre Channel) · Serie de chasis `USE7300M1X`
  (`cpqSsChassisSerialNumber`) · Controladora `msa1000` con WWN `2000001738AABB01`
- **6 discos físicos** SAS 10K de 900 GB (858 495 MB c/u) = 4.91 TB brutos
  (`capacidad_total_TB`); **RAID5** (`distribDataGuard`) → volumen lógico de 4 000 000 MB
  (bajo el máximo útil de 4 292 475 MB); **disco en la bahía 6 marcado `degraded`** a propósito
- Tarjeta HBA Fibre Channel: `fca-lpe1605` (HPE StoreFabric 16Gb dual-port), WWPN
  `20000090FA112201` usado como `mac_address` de la ficha (Fibre Channel no tiene MAC; ver nota
  en `MAPEO-STORAGE.md` sección 5.2)
- CPU: 2× Intel Xeon E5-2650 v3 (10 núcleos/20 hilos, 2.3 GHz) · RAM: 64 GB (4×16GB DDR4-2133)
- 2 ventiladores, 2 fuentes de poder (ambas `ok`), 2 puertos Ethernet (cpqnic, NO IF-MIB)
- **PRESTADO (NIMBLE-MIB):** IOPS ≈ 1200 lectura / 800 escritura, latencia ≈ 1.2 ms lectura /
  2.5 ms escritura, capacidad usada ≈ 1.91 TB (bajo el volumen lógico de 4 TB)
- **PRESTADO (FCMGMT-MIB):** tráfico de 2 puertos Fibre Channel del arreglo, valores fijos en
  hexadecimal (limitación documentada: snmpsim no puede aplicar variación `numeric` sobre
  `OCTET STRING`, ver `MAPEO-STORAGE.md` sección 10)

Ver [`MAPEO-STORAGE.md`](../../mibs/hpe-real/MAPEO-STORAGE.md) para el detalle completo de OID,
las reglas de coherencia de capacidades (RAID vs. volumen lógico vs. capacidad usada) y qué
campos son manuales/sin fuente/prestados.
