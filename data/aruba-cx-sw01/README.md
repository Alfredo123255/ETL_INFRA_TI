# Agente simulado: aruba-cx-sw01 (Aruba 6300M 48G PoE CLS4 /4SFP56, JL661A)

Agente SNMP simulado con [snmpsim](https://pypi.org/project/snmpsim/), poblado con datos
derivados de los MIB reales en [`mibs/ALL-Supported-MIBs/`](../../mibs/ALL-Supported-MIBs/) (ver
[`MAPEO-SWITCH.md`](../../mibs/ALL-Supported-MIBs/MAPEO-SWITCH.md) para el detalle de qué OID
corresponde a cada campo, y [`ANALISIS-SWITCH-ARUBA.md`](../../mibs/ANALISIS-SWITCH-ARUBA.md)
para el análisis de cobertura previo). El archivo de datos es
[`public.snmprec`](./public.snmprec).

Las secciones **CPU y RAM** de la ficha se completan con objetos **prestados** de
`mibs/hpe-real/` (`CPQSTDEQ-MIB` y `CPQSINFO-MIB`, árbol `1.3.6.1.4.1.232.*`): un switch
ArubaOS-CX real **no** expone esos OID; se usan aquí solo para no dejar esas secciones vacías en
la simulación. Están marcados con un bloque de comentario `#` en `public.snmprec` y documentados
en detalle en `MAPEO-SWITCH.md` (secciones 10 y 11). El ETL debe poder ignorar ese bloque al
consultar un switch Aruba real.

## Cómo levantarlo

Requiere `snmpsim` + `pysnmp>=6.2.0,<7.0.0` instalados (`pip install snmpsim "pysnmp>=6.2.0,<7.0.0"`).

Se usa el mismo wrapper [`data/run_responder.py`](../run_responder.py) que el resto de agentes
de este repositorio (evita el `RuntimeError: There is no current event loop in thread
'MainThread'` de `snmpsim-command-responder` en Python 3.12+/3.14).

Desde la raíz del repositorio:

```bash
python data/run_responder.py \
  --v3-engine-id=800000000153573031 \
  --v3-user=monitor_sw01 \
  --v3-auth-key='2JePukZ17WBQg10i3J3U' --v3-auth-proto=SHA \
  --v3-priv-key='ZynkEa6RTaPcFsqG1Oc5' --v3-priv-proto=AES \
  --agent-udpv4-endpoint=127.0.0.20:16600 \
  --data-dir="<ruta-absoluta-al-repo>\data\aruba-cx-sw01" \
  --cache-dir="<ruta-absoluta-al-repo>\logs\snmpsim-cache"
```

`--data-dir` y `--cache-dir` deben ser **rutas absolutas** (con rutas relativas snmpsim arma la
ruta del índice `.dbm` concatenando el string literal y falla con `FileNotFoundError`).

También se puede levantar junto con el resto de agentes vía
[`data/start_agents.bat`](../start_agents.bat).

## Puerto y transporte

| | |
|---|---|
| Host | `127.0.0.20` (loopback; Windows trata todo `127.0.0.0/8` como loopback, así que cada agente puede usar una IP distinta sin configuración adicional — ver `data/verify_agents.py` para la lista completa) |
| Puerto UDP | **16600** |
| Verificado libre con | `netstat -ano \| findstr :16600` antes de asignarlo |

## Credenciales SNMPv3

| Parámetro | Valor |
|---|---|
| Usuario (`securityName`) | `monitor_sw01` |
| Nivel de seguridad | `authPriv` |
| Protocolo de autenticación | `SHA` (usmHMACSHAAuthProtocol) |
| Clave de autenticación | `2JePukZ17WBQg10i3J3U` |
| Protocolo de privacidad | `AES` (usmAesCfb128Protocol) |
| Clave de privacidad | `ZynkEa6RTaPcFsqG1Oc5` |
| Engine ID (`--v3-engine-id`) | `800000000153573031` (fijo; `53573031` = hex de "SW01") |
| **Contexto SNMPv3** | `public` |

⚠️ **El contexto importa.** Igual que en los demás agentes: un cliente que use `ContextData()`
sin `contextName="public"` explícito ve su solicitud descartada en silencio. Ver
[`data/verify_agents.py`](../verify_agents.py).

Estas claves son solo para este entorno de prueba local (no usar en producción).

## Verificación rápida

```bash
python data/verify_agents.py
```

O con `snmpget` (net-snmp) si está disponible:

```bash
snmpget -v3 -u monitor_sw01 -l authPriv \
  -a SHA -A '2JePukZ17WBQg10i3J3U' \
  -x AES -X 'ZynkEa6RTaPcFsqG1Oc5' \
  -n public \
  127.0.0.20:16600 1.3.6.1.2.1.1.1.0
```

## Índice de caché

snmpsim indexa `public.snmprec` en un `.dbm` bajo `--cache-dir` la primera vez (o cuando el
archivo cambia). Si se edita `public.snmprec` a mano y el agente ya está corriendo, hace falta
reiniciarlo (o pasar `--force-index-rebuild`) para que tome los cambios.

## Especificaciones simuladas (resumen)

- Hostname: `aruba-cx-sw01` · Identidad: Aruba 6300M 48G PoE CLS4 /4SFP56 (**JL661A**),
  `sysObjectID = 1.3.6.1.4.1.47196.4.1.1.1.103` (resuelto con pysnmp desde
  `ARUBAWIRED-NETWORKING-OID.mib`, no derivado a mano)
- Serie de chasis: `SG42AR001W` (`arubaWiredModuleSerialNumber`) · Firmware:
  `GL.10.16.1030` (imagen `primary`, `arubaWiredSwitchImageVersion`)
- Ubicación distinta a la de los servidores: `DataCenter-1 / Rack A05 / ToR Networking`
- **52 puertos físicos**: 48 de acceso GbE PoE (`1/1/1`..`1/1/48`) + 4 uplinks SFP56
  (`1/1/49`..`1/1/52`). Distribución de estado: 38 up/up, 9 up/down, **1 puerto (`1/1/48`) con
  `ifAdminStatus` down a propósito**; uplinks `1/1/49-50` up/up, `1/1/51-52` up/down
  (40 puertos "ocupados" en total)
- Además del rango físico, 3 interfaces **no físicas** para que el ETL demuestre el filtrado:
  `vlan1` (`propVirtual`), `lag1` (`ieee8023adLag`, sin miembros activos) y `mgmt`
  (`other`, IP de gestión `10.10.12.20`)
- Tráfico: `ARUBAWIRED-INTERFACE-MIB` (tasas fijas ya calculadas por el switch, intervalo 30 s) +
  `IF-MIB` `ifHCInOctets`/`ifHCOutOctets` (Counter64) e `ifInErrors`/`ifOutErrors` (Counter32)
  **creciendo en vivo** (variación `numeric` de snmpsim) en los puertos `up`
- 4 sensores de temperatura (`ARUBAWIRED-TEMPSENSOR-MIB`), representativo = `Chassis-Ambient`
  (28.0 °C); consumo total del chasis = 210 W (`ARUBAWIRED-POWER-STAT-MIB`)
- 2 fuentes de poder (`ARUBAWIRED-POWERSUPPLY-MIB`): PSU1 `ok(1)` a 210/650 W, **PSU2
  `warning(10)`** a 0/650 W
- 3 bandejas de ventilador (`ARUBAWIRED-FAN-MIB`): 2 en `ok(4)`, **1 en `fault(5)`** (100 RPM)
- Uso de CPU/RAM del sistema (`ARUBAWIRED-SYSTEMINFO-MIB`): 18 % CPU, 42 % memoria
- CPU y RAM físicos **PRESTADOS** de HPE (`CPQSTDEQ-MIB`/`CPQSINFO-MIB`, ver nota arriba): 1 CPU
  MIPS de 4 núcleos/4 hilos a 1.2 GHz (32 KB L1 + 512 KB L2, sin L3), 1 módulo de RAM SK Hynix
  DDR3-1600 de 4 GB

Ver [`MAPEO-SWITCH.md`](../../mibs/ALL-Supported-MIBs/MAPEO-SWITCH.md) para el detalle completo
de OID, qué campos son manuales/sin fuente/prestados, y las reglas de traducción de cada enum de
estado de Aruba (no se reutilizan los valores numéricos de los enums HPE).
