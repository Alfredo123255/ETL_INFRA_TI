# Agente simulado: hpe-dl380-01 (HPE ProLiant DL380 Gen10)

Agente SNMP simulado con [snmpsim](https://pypi.org/project/snmpsim/), poblado con datos
derivados de los MIB reales en [`mibs/hpe-real/`](../../mibs/hpe-real/) (ver
[`MAPEO-SERVIDOR.md`](../../mibs/hpe-real/MAPEO-SERVIDOR.md) para el detalle de qué OID
corresponde a cada campo). El archivo de datos es [`public.snmprec`](./public.snmprec).

## Cómo levantarlo

Requiere `snmpsim` + `pysnmp>=6.2.0,<7.0.0` instalados (`pip install snmpsim "pysnmp>=6.2.0,<7.0.0"`).

En Python 3.12+/3.14, `snmpsim-command-responder` falla con
`RuntimeError: There is no current event loop in thread 'MainThread'` porque pysnmp todavía
depende de que `asyncio.get_event_loop()` cree un loop implícito. Por eso se usa el wrapper
[`data/run_responder.py`](../run_responder.py) en vez de invocar el binario `snmpsim-command-responder`
directamente — crea el event loop explícitamente antes de arrancar el agente, sin cambiar ningún
otro comportamiento.

Desde la raíz del repositorio:

```bash
python data/run_responder.py \
  --v3-engine-id=8000000001444c333830 \
  --v3-user=monitor_dl380 \
  --v3-auth-key='Kr7aY5nT2LdUco2B5IAZ' --v3-auth-proto=SHA \
  --v3-priv-key='GpoJkRAhPOZg3vA4qHyT' --v3-priv-proto=AES \
  --agent-udpv4-endpoint=127.0.0.11:16100 \
  --data-dir="<ruta-absoluta-al-repo>\data\hpe-dl380-01" \
  --cache-dir="<ruta-absoluta-al-repo>\logs\snmpsim-cache"
```

`--data-dir` y `--cache-dir` deben ser **rutas absolutas**: con rutas relativas del estilo
`./data/hpe-dl380-01`, snmpsim arma la ruta del índice `.dbm` concatenando el string literal y
falla con `FileNotFoundError` porque el subdirectorio intermedio no existe.

## Puerto y transporte

| | |
|---|---|
| Host | `127.0.0.11` (loopback; Windows trata todo `127.0.0.0/8` como loopback, así que cada agente puede usar una IP distinta sin configuración adicional — ver `data/verify_agents.py` para la lista completa) |
| Puerto UDP | **16100** |
| Verificado libre con | `netstat -ano \| grep 16100` antes de asignarlo |

## Credenciales SNMPv3

| Parámetro | Valor |
|---|---|
| Usuario (`securityName`) | `monitor_dl380` |
| Nivel de seguridad | `authPriv` |
| Protocolo de autenticación | `SHA` (usmHMACSHAAuthProtocol) |
| Clave de autenticación | `Kr7aY5nT2LdUco2B5IAZ` |
| Protocolo de privacidad | `AES` (usmAesCfb128Protocol) |
| Clave de privacidad | `GpoJkRAhPOZg3vA4qHyT` |
| Engine ID (`--v3-engine-id`) | `8000000001444c333830` (fijo, no `auto`, para que no cambie entre reinicios) |
| **Contexto SNMPv3** | `public` |

⚠️ **El contexto importa.** snmpsim registra sus datos bajo el contexto `"public"` (se ve en el
log de arranque: `SNMPv3 Context Name: ... or public`). Un cliente que use `ContextData()` sin
`contextName="public"` explícito ve su solicitud **descifrada correctamente pero descartada en
silencio** (sin ningún error ni respuesta) porque el agente no encuentra ese "contexto vacío" —
no es un fallo de autenticación, solo hay que fijar el nombre de contexto. Ver
[`data/verify_agents.py`](../verify_agents.py) para el patrón correcto.

Estas claves son solo para este entorno de prueba local (no usar en producción).

## Verificación rápida

```bash
python data/verify_agents.py
```

O con `snmpget` (net-snmp) si está disponible:

```bash
snmpget -v3 -u monitor_dl380 -l authPriv \
  -a SHA -A 'Kr7aY5nT2LdUco2B5IAZ' \
  -x AES -X 'GpoJkRAhPOZg3vA4qHyT' \
  -n public \
  127.0.0.11:16100 1.3.6.1.2.1.1.1.0
```

## Índice de caché

snmpsim indexa `public.snmprec` en un `.dbm` bajo `--cache-dir` la primera vez (o cuando el
archivo cambia). Si se edita `public.snmprec` a mano y el agente ya está corriendo, hace falta
reiniciarlo (o pasar `--force-index-rebuild`) para que tome los cambios.

## Especificaciones simuladas (resumen)

- Hostname: `hpe-dl380-01` · Serie: `CZ38010ABC` · Modelo: ProLiant DL380 Gen10
- 2x Intel Xeon Gold 6230 (20 núcleos / 40 hilos, 2.1 GHz) · 128 GB RAM (4x32GB), con número de
  serie por módulo (`cpqSiMemModuleSerialNo`)
- RAID10 sobre 4 discos SAS 600GB 15K (controladora Smart Array P408i-a, con
  `cpqDaCntlrSerialNumber`); `cpqDaLogDrvSize` = 1.143.552 MB, la capacidad útil real de RAID10
  sobre 4x571.776 MB (no la suma bruta)
- 2 fuentes de poder (una marcada `failed` a propósito, para probar el estado Apagado)
- 2 ventiladores, 2 sensores de temperatura
- 2 puertos de red (`cpqNicIfPhysAdapterTable`): NIC1 (331i embebida, slot 0) 1 Gb y NIC2
  (562FLR-SFP+ add-in, slot 1) 10 Gb, cada una con MAC propia, velocidad
  (`cpqNicIfPhysAdapterSpeed`/`SpeedMbps`), estado (`cpqNicIfPhysAdapterStatus`) y contadores de
  tráfico/errores (`InOctets`/`OutOctets`/`FCSErrors`/`AlignmentErrors`/`BadReceives`/
  `BadTransmits`) que crecen en vivo (variación `numeric` de snmpsim, una tasa distinta por
  puerto)
- IP-MIB: `10.10.12.11/24`
- Sistema operativo simulado: Microsoft Windows Server 2019 Standard

Ver [`MAPEO-SERVIDOR.md`](../../mibs/hpe-real/MAPEO-SERVIDOR.md) para qué campos no tienen OID
real disponible (no se inventaron valores para esos).
