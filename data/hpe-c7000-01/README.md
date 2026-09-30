# Agente simulado: hpe-c7000-01 (HPE BladeSystem c7000 Enclosure G2)

Agente SNMP simulado con [snmpsim](https://pypi.org/project/snmpsim/), poblado con datos
derivados del MIB real `CPQRACK-MIB` en [`mibs/hpe-real/`](../../mibs/hpe-real/) (ver
[`MAPEO-CHASIS.md`](../../mibs/hpe-real/MAPEO-CHASIS.md) para el detalle de qué OID corresponde
a cada campo). El archivo de datos es [`public.snmprec`](./public.snmprec).

## Cómo levantarlo

Requiere `snmpsim` + `pysnmp>=6.2.0,<7.0.0` instalados (`pip install snmpsim "pysnmp>=6.2.0,<7.0.0"`).
Usa el mismo wrapper [`data/run_responder.py`](../run_responder.py) que los servidores (necesario
en Python 3.12+/3.14 porque `snmpsim-command-responder` depende de un event loop implícito que
`asyncio.get_event_loop()` ya no crea solo).

Desde la raíz del repositorio:

```bash
python data/run_responder.py \
  --v3-engine-id=80000000014337303030 \
  --v3-user=monitor_c7000 \
  --v3-auth-key='cy8EcO4BePPAN9Os5zts' --v3-auth-proto=SHA \
  --v3-priv-key='NR2yILtdOtWShA70stgf' --v3-priv-proto=AES \
  --agent-udpv4-endpoint=127.0.0.15:16300 \
  --data-dir="<ruta-absoluta-al-repo>\data\hpe-c7000-01" \
  --cache-dir="<ruta-absoluta-al-repo>\logs\snmpsim-cache"
```

`--data-dir` y `--cache-dir` deben ser **rutas absolutas** (mismo motivo que los servidores: con
rutas relativas snmpsim arma la ruta del índice `.dbm` mal y falla con `FileNotFoundError`).

## Puerto y transporte

| | |
|---|---|
| Host | `127.0.0.15` (loopback; Windows trata todo `127.0.0.0/8` como loopback, así que cada agente puede usar una IP distinta sin configuración adicional — ver `data/verify_agents.py` para la lista completa) |
| Puerto UDP | **16300** (distinto de 16100 y 16200, usados por los servidores) |
| Verificado libre con | `netstat -ano \| grep 16300` antes de asignarlo |

## Credenciales SNMPv3

| Parámetro | Valor |
|---|---|
| Usuario (`securityName`) | `monitor_c7000` |
| Nivel de seguridad | `authPriv` |
| Protocolo de autenticación | `SHA` (usmHMACSHAAuthProtocol) |
| Clave de autenticación | `cy8EcO4BePPAN9Os5zts` |
| Protocolo de privacidad | `AES` (usmAesCfb128Protocol) |
| Clave de privacidad | `NR2yILtdOtWShA70stgf` |
| Engine ID (`--v3-engine-id`) | `80000000014337303030` (fijo; los últimos 5 bytes son `"C7000"` en ASCII, mismo patrón mnemotécnico que `...444c333830`="DL380" y `...444c333630`="DL360") |
| **Contexto SNMPv3** | `public` |

⚠️ **El contexto importa.** Igual que en los servidores: sin `ContextData(contextName="public")`
explícito, el agente descarta la solicitud en silencio después de descifrarla correctamente. Ver
[`data/verify_agents.py`](../verify_agents.py).

Estas claves son solo para este entorno de prueba local (no usar en producción). Usuario y claves
son propios de este agente y distintos de los de `hpe-dl380-01`/`hpe-dl360-01`.

## Verificación rápida

```bash
python data/verify_agents.py
```

O con `snmpget` (net-snmp) si está disponible:

```bash
snmpget -v3 -u monitor_c7000 -l authPriv \
  -a SHA -A 'cy8EcO4BePPAN9Os5zts' \
  -x AES -X 'NR2yILtdOtWShA70stgf' \
  -n public \
  127.0.0.15:16300 1.3.6.1.2.1.1.1.0
```

## Índice de caché

snmpsim indexa `public.snmprec` en un `.dbm` bajo `--cache-dir` la primera vez (o cuando el
archivo cambia). Si se edita `public.snmprec` a mano y el agente ya está corriendo, hace falta
reiniciarlo (o pasar `--force-index-rebuild`) para que tome los cambios.

## Especificaciones simuladas (resumen)

- Hostname: `hpe-c7000-01` · Serie: `CZ7000ABCD` · Modelo: BladeSystem c7000 Enclosure G2
- 8 slots (`cantidad_slots`): slot 1 = `hpe-bl460c-01` (Ocupado, agente propio en
  [`data/hpe-bl460c-01`](../hpe-bl460c-01/)), slot 2 = `hpe-bl460c-02` (Ocupado, agente propio en
  [`data/hpe-bl460c-02`](../hpe-bl460c-02/)), slot 3 = `hpe-bl460c-03` (Degradado — presente pero
  con falla, para probar ese estado; sin agente propio), slots 4-8 = Libres
- 4 fuentes de poder (una marcada `failed`/Apagado, a propósito) · 4 ventiladores (uno marcado
  Degradado) · 4 módulos de interconexión de red (Virtual Connect / switches Ethernet de blade)
- Medidor de potencia total del chasis (`cpqRackPowerMeterWattage`): 3200 W
- IF-MIB (+ ifXTable) del módulo de interconexión de la bahía 1 (Virtual Connect Flex-10/10D):
  8 puertos externos `X1`..`X8` (10 Gb) y 4 internos `d1`..`d4` (10 Gb), todos arriba, con
  contadores de tráfico y errores creciendo (variación `numeric` de snmpsim, tasa distinta por
  puerto) — demuestra el filtrado externo/interno, ya que `CPQRACK-MIB` no expone puertos
- HPVCMODULE-MIB: `vcModulePortTable` relaciona cada uno de esos 12 puertos
  (`vcModulePort` 1-12) con su fila de IF-MIB vía `vcModulePortIfIndex`

Ver [`MAPEO-CHASIS.md`](../../mibs/hpe-real/MAPEO-CHASIS.md) para qué campos no tienen OID real
disponible en `CPQRACK-MIB` (no se inventaron valores para esos) — en particular, las tarjetas de
red/interconnects no tienen ningún campo de condición/salud en este MIB.
