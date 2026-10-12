# Huawei E9000 con módulo MM910

Agente SNMPv3 de laboratorio basado en `OSCA-MIB` del paquete MM910 V763 de
[`mibs/huawei`](../../mibs/huawei/). Su archivo editable es
[`public.snmprec`](public.snmprec). Expone serie de chasis `HWE9000LAB001`,
salud, consumo, temperatura, dos fuentes, cuatro ventiladores y dos bahías:
la 1 contiene `huawei-ch121-v5-01` (serie `HWCH121V5001`) y la 2 está libre.

| Dato | Valor |
|---|---|
| IP y puerto | `127.0.0.42:17200` |
| Usuario | `monitor_hwe9000` |
| Clave de autenticación | `HwE9000Lab2026Auth` |
| SNMPv3 | SHA / AES, contexto `public` |
| Clave de privacidad | Igual a la de autenticación |

Desde la raíz del ETL: `data/start_agents.bat` inicia todos los agentes en
ventanas independientes. Para detener:
`data/stop_agents.bat`. Consulta de prueba: `python -B data/verify_agents.py --solo huawei-e9000-01`.

El ETL identifica este chasis Huawei, sus bahías y componentes, y lo puede
registrar y actualizar. La serie FRU de la bahía ocupada permite vincular el
blade ya registrado en el mismo datacenter.
