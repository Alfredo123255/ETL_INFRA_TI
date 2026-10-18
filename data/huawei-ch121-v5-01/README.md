# Huawei CH121 V5 (blade)

Agente SNMPv3 de laboratorio basado en `HUAWEI-SERVER-iBMC-MIB` V670 de
[`mibs/huawei`](../../mibs/huawei/). Su archivo editable es
[`public.snmprec`](public.snmprec). El blade está en la bahía 1 del E9000:
reporta serie `HWCH121V5001` y serie de chasis `HWE9000LAB001`, iguales a las
que expone el agente del chasis. CPU, RAM y discos usan OID del iBMC; fuentes y
ventiladores compartidos se consultan en el E9000.

| Dato | Valor |
|---|---|
| IP y puerto | `127.0.0.41:17100` |
| Usuario | `Administrator` |
| Clave de autenticación | `Admin@9000` |
| SNMPv3 | SHA / AES, contexto `public` |
| Clave de privacidad | Igual a la de autenticación |

Desde la raíz del ETL: `data/start_agents.bat` inicia todos los agentes en
ventanas independientes. Para detener:
`data/stop_agents.bat`. Consulta de prueba: `python -B data/verify_agents.py --solo huawei-ch121-v5-01`.

El ETL identifica este equipo por SNMP como blade Huawei. La asociación a la
bahía del E9000 se hace por la serie FRU al registrar o actualizar el chasis;
ambos activos deben pertenecer al mismo datacenter.
