# Agente simulado: hpe-bl460c-02 (HPE ProLiant BL460c Gen10, tipo BLADE)

Agente SNMP simulado con [snmpsim](https://pypi.org/project/snmpsim/), poblado con datos
derivados de los MIB reales en [`mibs/hpe-real/`](../../mibs/hpe-real/) (ver
[`MAPEO-SERVIDOR.md`](../../mibs/hpe-real/MAPEO-SERVIDOR.md) para el detalle de qué OID
corresponde a cada campo). El archivo de datos es [`public.snmprec`](./public.snmprec).

Este agente replica el patrón de [`hpe-dl380-01`](../hpe-dl380-01/) / [`hpe-dl360-01`](../hpe-dl360-01/)
pero para un servidor **tipo BLADE**: ocupa el **slot 2** del chasis
[`hpe-c7000-01`](../hpe-c7000-01/) (ver `cpqRackServerBladeName.1.1.2` en su `public.snmprec`,
que ahora reporta `hpe-bl460c-02`). El número de serie (`numero_serie` /
`cpqSiSysSerialNum.0` = `SN002BLD`) se hizo coincidir a propósito con el que el chasis ya
reporta para ese slot (`cpqRackServerBladeSerialNum.1.1.2`), para que ambos agentes describan
el mismo blade de forma consistente.

**Alcance deliberadamente distinto al de un servidor rack:** este agente sólo expone lo que la
ficha de un servidor *blade* necesita (datos generales, CPU, RAM, discos + controladora RAID,
temperatura, consumo e IP del sistema operativo). **No** expone tabla de tarjetas de red
(`cpqNicIfPhysAdapterTable`), ventiladores (`cpqHeFltTolFanTable`) ni fuentes de poder
(`cpqHeFltTolPowerSupplyTable`), ni IF-MIB propio: un blade no tiene NIC, ventiladores ni fuentes
de poder individuales — todo eso es compartido a nivel de chasis y ya lo reporta
[`hpe-c7000-01`](../hpe-c7000-01/) (`cpqRackNetConnectorTable`, `cpqRackCommonEnclosureFanTable`,
`cpqRackPowerSupplyTable`, y el IF-MIB del módulo de interconexión). Ver
[`MAPEO-SERVIDOR.md`](../../mibs/hpe-real/MAPEO-SERVIDOR.md) sección "Servidores tipo BLADE".

## Cómo levantarlo

Requiere `snmpsim` + `pysnmp>=6.2.0,<7.0.0` instalados (`pip install snmpsim "pysnmp>=6.2.0,<7.0.0"`).
Usa el mismo wrapper [`data/run_responder.py`](../run_responder.py) que el resto de agentes
(necesario en Python 3.12+/3.14 porque `snmpsim-command-responder` depende de un event loop
implícito que `asyncio.get_event_loop()` ya no crea solo).

Desde la raíz del repositorio:

```bash
python data/run_responder.py \
  --v3-engine-id=8000000001424c433032 \
  --v3-user=monitor_bl460c02 \
  --v3-auth-key='Ht4RxQ8kMbZ3vNp6Ld1J' --v3-auth-proto=SHA \
  --v3-priv-key='Sc9WjE2yTfL7uKq4Gz5V' --v3-priv-proto=AES \
  --agent-udpv4-endpoint=127.0.0.14:16500 \
  --data-dir="<ruta-absoluta-al-repo>\data\hpe-bl460c-02" \
  --cache-dir="<ruta-absoluta-al-repo>\logs\snmpsim-cache"
```

`--data-dir` y `--cache-dir` deben ser **rutas absolutas** (mismo motivo que el resto de
agentes: con rutas relativas snmpsim arma la ruta del índice `.dbm` mal y falla con
`FileNotFoundError`).

## Puerto y transporte

| | |
|---|---|
| Host | `127.0.0.14` (loopback; Windows trata todo `127.0.0.0/8` como loopback, así que cada agente puede usar una IP distinta sin configuración adicional — ver `data/verify_agents.py` para la lista completa) |
| Puerto UDP | **16500** (distinto de 16100/16200/16300/16400 usados por los otros agentes) |
| Verificado libre con | `netstat -ano \| grep 16500` antes de asignarlo |

## Credenciales SNMPv3

| Parámetro | Valor |
|---|---|
| Usuario (`securityName`) | `monitor_bl460c02` |
| Nivel de seguridad | `authPriv` |
| Protocolo de autenticación | `SHA` (usmHMACSHAAuthProtocol) |
| Clave de autenticación | `Ht4RxQ8kMbZ3vNp6Ld1J` |
| Protocolo de privacidad | `AES` (usmAesCfb128Protocol) |
| Clave de privacidad | `Sc9WjE2yTfL7uKq4Gz5V` |
| Engine ID (`--v3-engine-id`) | `8000000001424c433032` (fijo; los últimos 5 bytes son `"BLC02"` en ASCII, mismo patrón mnemotécnico que `...444c333830`="DL380", `...444c333630`="DL360", `...4337303030`="C7000" y `...424c433031`="BLC01") |
| **Contexto SNMPv3** | `public` |

⚠️ **El contexto importa.** Igual que en los demás agentes: sin `ContextData(contextName="public")`
explícito, el agente descarta la solicitud en silencio después de descifrarla correctamente. Ver
[`data/verify_agents.py`](../verify_agents.py).

Estas claves son solo para este entorno de prueba local (no usar en producción). Usuario y
claves son propios de este agente y distintos de los del resto.

## Verificación rápida

```bash
python data/verify_agents.py
```

O con `snmpget` (net-snmp) si está disponible:

```bash
snmpget -v3 -u monitor_bl460c02 -l authPriv \
  -a SHA -A 'Ht4RxQ8kMbZ3vNp6Ld1J' \
  -x AES -X 'Sc9WjE2yTfL7uKq4Gz5V' \
  -n public \
  127.0.0.14:16500 1.3.6.1.2.1.1.1.0
```

## Índice de caché

snmpsim indexa `public.snmprec` en un `.dbm` bajo `--cache-dir` la primera vez (o cuando el
archivo cambia). Si se edita `public.snmprec` a mano y el agente ya está corriendo, hace falta
reiniciarlo (o pasar `--force-index-rebuild`) para que tome los cambios.

## Especificaciones simuladas (resumen)

- Hostname: `hpe-bl460c-02` · Serie: `SN002BLD` (igual a la que reporta el chasis para el slot 2)
  · Modelo: ProLiant BL460c Gen10
- 2x Intel Xeon Silver 4210R (10 núcleos / 20 hilos cada uno, 2.4 GHz)
- 64 GB RAM (4x16GB), con número de serie por módulo (`cpqSiMemModuleSerialNo`)
- RAID1 sobre 2 discos NVMe 480GB (controladora Smart Array P204i-c, con
  `cpqDaCntlrSerialNumber`)
- 2 sensores de temperatura · medidor de consumo eléctrico (`cpqHePowerMeterCurrReading`)
- IP-MIB: `10.10.12.14/24` (este agente no expone IF-MIB propio — ver nota de alcance arriba —
  por lo que `ipAdEntIfIndex` usa `1` como referencia genérica, sin tabla de interfaces local)
- Sistema operativo simulado: Ubuntu Server 22.04.3 LTS
- Sin tarjetas de red, ventiladores ni fuentes de poder propias (las reporta el chasis, ver nota
  de alcance arriba)

Ver [`MAPEO-SERVIDOR.md`](../../mibs/hpe-real/MAPEO-SERVIDOR.md) para qué campos no tienen OID
real disponible (no se inventaron valores para esos).
