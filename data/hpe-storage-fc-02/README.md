# Agente simulado: hpe-storage-fc-02 (HPE ProLiant DL360 Gen9 + HPE StorageWorks EVA4400 FC)

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
  --v3-engine-id=800000000153543032 \
  --v3-user=monitor_storagefc02 \
  --v3-auth-key='SMkMLpmciBdaLR9pfDux' --v3-auth-proto=SHA \
  --v3-priv-key='2VcFacU3YHQ1CqwgAg7D' --v3-priv-proto=AES \
  --agent-udpv4-endpoint=127.0.0.31:16800 \
  --data-dir="<ruta-absoluta-al-repo>\data\hpe-storage-fc-02" \
  --cache-dir="<ruta-absoluta-al-repo>\logs\snmpsim-cache"
```

`--data-dir` y `--cache-dir` deben ser **rutas absolutas**. También se puede levantar junto con
el resto de agentes vía [`data/start_agents.bat`](../start_agents.bat).

## Puerto y transporte

| | |
|---|---|
| Host | `127.0.0.31` (loopback; Windows trata todo `127.0.0.0/8` como loopback, así que cada agente puede usar una IP distinta sin configuración adicional — ver `data/verify_agents.py` para la lista completa) |
| Puerto UDP | **16800** |
| Verificado libre con | `netstat -ano \| findstr :16800` antes de asignarlo |

## Credenciales SNMPv3

| Parámetro | Valor |
|---|---|
| Usuario (`securityName`) | `monitor_storagefc02` |
| Nivel de seguridad | `authPriv` |
| Protocolo de autenticación | `SHA` (usmHMACSHAAuthProtocol) |
| Clave de autenticación | `SMkMLpmciBdaLR9pfDux` |
| Protocolo de privacidad | `AES` (usmAesCfb128Protocol) |
| Clave de privacidad | `2VcFacU3YHQ1CqwgAg7D` |
| Engine ID (`--v3-engine-id`) | `800000000153543032` (fijo; `53543032` = hex de "ST02") |
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
snmpget -v3 -u monitor_storagefc02 -l authPriv \
  -a SHA -A 'SMkMLpmciBdaLR9pfDux' \
  -x AES -X '2VcFacU3YHQ1CqwgAg7D' \
  -n public \
  127.0.0.31:16800 1.3.6.1.2.1.1.1.0
```

## Especificaciones simuladas (resumen)

- Servidor: ProLiant DL360 Gen9 · Serie `CZ2513021K` · `sysObjectID =
  1.3.6.1.4.1.232.9.4.15` (siguiendo el patrón numérico de los demás agentes de servidor) ·
  Ubicación `DataCenter-1 / Rack B04 / U12`
- Arreglo: **HPE StorageWorks Enterprise Virtual Array 4400** (Fibre Channel) · Serie de chasis
  `USE7400M2Y` (`cpqSsChassisSerialNumber`) · Controladora `hsv110` con WWN `2001001738CCDD02`
- **8 discos físicos** SAS 15K de 600 GB (571 776 MB c/u) = 4.36 TB brutos
  (`capacidad_total_TB`); **RAID1/mirroring** → volumen lógico de 2 000 000 MB (bajo el máximo
  útil de 2 287 104 MB = 50% del bruto)
- Tarjeta HBA Fibre Channel: `fca-sn1600e-2p` (HPE StoreFabric 16Gb dual-port), WWPN
  `20000090FA334402` usado como `mac_address` de la ficha (Fibre Channel no tiene MAC; ver nota
  en `MAPEO-STORAGE.md` sección 5.2)
- CPU: 2× Intel Xeon E5-2640 v4 (10 núcleos/20 hilos, 2.4 GHz) · RAM: 32 GB (2×16GB DDR4-2400)
- 2 ventiladores; **2 fuentes de poder, la fuente de la bahía 2 marcada `failed` a propósito**
  (`cpqHeFltTolPowerSupplyCondition`); 1 puerto Ethernet (cpqnic, NO IF-MIB)
- **PRESTADO (NIMBLE-MIB):** IOPS ≈ 600 lectura / 400 escritura, latencia ≈ 0.8 ms lectura /
  1.8 ms escritura, capacidad usada ≈ 1.14 TB (bajo el volumen lógico de 2 TB)
- **PRESTADO (FCMGMT-MIB):** tráfico de 2 puertos Fibre Channel del arreglo, valores fijos en
  hexadecimal (limitación documentada: snmpsim no puede aplicar variación `numeric` sobre
  `OCTET STRING`, ver `MAPEO-STORAGE.md` sección 10)

Ver [`MAPEO-STORAGE.md`](../../mibs/hpe-real/MAPEO-STORAGE.md) para el detalle completo de OID,
las reglas de coherencia de capacidades (RAID vs. volumen lógico vs. capacidad usada) y qué
campos son manuales/sin fuente/prestados.
