# Huawei FusionServer Pro 2288H V5 (rack)

Agente SNMPv3 de laboratorio basado en `HUAWEI-SERVER-iBMC-MIB` V502 de
[`mibs/huawei`](../../mibs/huawei/). Su archivo editable es
[`public.snmprec`](public.snmprec). Incluye CPU, RAM DDR4, discos, fuentes AC,
ventiladores, tarjetas de red, IF-MIB y consumo eléctrico. Las series y valores
son simulados; los OID Huawei y sus tipos proceden del MIB.

| Dato | Valor |
|---|---|
| IP y puerto | `127.0.0.40:17000` |
| Usuario | `monitor_hw2288` |
| Clave de autenticación | `Hw2288Lab2026Auth` |
| SNMPv3 | SHA / AES, contexto `public` |
| Clave de privacidad | Igual a la de autenticación |

Desde la raíz del ETL: `data/start_agents.bat` inicia todos los agentes en
ventanas independientes. Para detener:
`data/stop_agents.bat`. Consulta de prueba: `python -B data/verify_agents.py --solo huawei-2288h-v5-01`.

En el formulario usa solo IP:puerto, usuario y clave. El ETL identifica este
equipo por SNMP como servidor Huawei rack y puede registrarlo y actualizarlo.
