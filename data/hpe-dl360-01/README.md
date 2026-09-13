# Agente simulado: hpe-dl360-01 (HPE ProLiant DL360 Gen10)

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
  --v3-engine-id=8000000001444c333630 \
  --v3-user=monitor_dl360 \
  --v3-auth-key='3nRFCWnSuDougjTVD3SV' --v3-auth-proto=SHA \
  --v3-priv-key='Wru30SG1uouCjtcd5h7P' --v3-priv-proto=AES \
  --agent-udpv4-endpoint=127.0.0.1:16200 \
  --data-dir="<ruta-absoluta-al-repo>\data\hpe-dl360-01" \
  --cache-dir="<ruta-absoluta-al-repo>\logs\snmpsim-cache"
```

`--data-dir` y `--cache-dir` deben ser **rutas absolutas**: con rutas relativas del estilo
`./data/hpe-dl360-01`, snmpsim arma la ruta del índice `.dbm` concatenando el string literal y
falla con `FileNotFoundError` porque el subdirectorio intermedio no existe.

## Puerto y transporte

| | |
|---|---|
| Host | `127.0.0.1` (sólo loopback) |
| Puerto UDP | **16200** |
| Verificado libre con | `netstat -ano \| grep 16200` antes de asignarlo |

## Credenciales SNMPv3

| Parámetro | Valor |
|---|---|
| Usuario (`securityName`) | `monitor_dl360` |
| Nivel de seguridad | `authPriv` |
| Protocolo de autenticación | `SHA` (usmHMACSHAAuthProtocol) |
| Clave de autenticación | `3nRFCWnSuDougjTVD3SV` |
| Protocolo de privacidad | `AES` (usmAesCfb128Protocol) |
| Clave de privacidad | `Wru30SG1uouCjtcd5h7P` |
| Engine ID (`--v3-engine-id`) | `8000000001444c333630` (fijo, no `auto`, para que no cambie entre reinicios) |
| **Contexto SNMPv3** | `public` |

⚠️ **El contexto importa.** snmpsim registra sus datos bajo el contexto `"public"` (se ve en el
log de arranque: `SNMPv3 Context Name: ... or public`). Un cliente que use `ContextData()` sin
`contextName="public"` explícito ve su solicitud **descifrada correctamente pero descartada en
silencio** (sin ningún error ni respuesta) porque el agente no encuentra ese "contexto vacío" —
no es un fallo de autenticación, solo hay que fijar el nombre de contexto. Ver
[`data/verify_agents.py`](../verify_agents.py) para el patrón correcto.

Estas claves son solo para este entorno de prueba local (no usar en producción). Usuario y claves
son propios de este agente y distintos de los de `hpe-dl380-01`.

## Verificación rápida

```bash
python data/verify_agents.py
```

O con `snmpget` (net-snmp) si está disponible:

```bash
snmpget -v3 -u monitor_dl360 -l authPriv \
  -a SHA -A '3nRFCWnSuDougjTVD3SV' \
  -x AES -X 'Wru30SG1uouCjtcd5h7P' \
  -n public \
  127.0.0.1:16200 1.3.6.1.2.1.1.1.0
```

## Índice de caché

snmpsim indexa `public.snmprec` en un `.dbm` bajo `--cache-dir` la primera vez (o cuando el
archivo cambia). Si se edita `public.snmprec` a mano y el agente ya está corriendo, hace falta
reiniciarlo (o pasar `--force-index-rebuild`) para que tome los cambios.

## Especificaciones simuladas (resumen)

- Hostname: `hpe-dl360-01` · Serie: `CZ36010XYZ` · Modelo: ProLiant DL360 Gen10
- 1x Intel Xeon Silver 4210R (10 núcleos / 20 hilos, 2.4 GHz) · 64 GB RAM (4x16GB)
- RAID1 sobre 2 discos SSD 480GB (controladora Smart Array E208i-a)
- 2 fuentes de poder (ambas sanas) · 2 ventiladores · 2 sensores de temperatura
- 2 NIC (una marcada `degraded` a propósito, para probar el estado Degradado)
- Sistema operativo simulado: Red Hat Enterprise Linux Server 8.6

Ver [`MAPEO-SERVIDOR.md`](../../mibs/hpe-real/MAPEO-SERVIDOR.md) para qué campos no tienen OID
real disponible (no se inventaron valores para esos).
