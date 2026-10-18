# Huawei OceanStor Dorado 5000 V6

Agente SNMPv3 de laboratorio basado en los MIB de OceanStor Dorado 6.1.6 de
[`mibs/huawei`](../../mibs/huawei/). Su archivo editable es
[`public.snmprec`](public.snmprec). Expone serie de arreglo, capacidad,
dos controladoras, seis SSD NVMe, dos fuentes AC, cuatro ventiladores,
128 GB de memoria por controladora (capacidad total, sin datos de DIMM),
un pool, una LUN, dos puertos FC y métricas IOPS/latencia por nodo. Capacidad y rendimiento usan
los OID y unidades declarados por `ISM-STORAGE-SVC-MIB`,
`HUAWEI-STORAGE-HARDWARE-MIB`, `HUAWEI-STORAGE-SPACE-MIB` e
`ISM-PERFORMANCE-MIB`.

| Dato | Valor |
|---|---|
| IP y puerto | `127.0.0.43:17300` |
| Usuario | `Administrator` |
| Clave de autenticación | `Admin@9000` |
| SNMPv3 | SHA / AES, contexto `public` |
| Clave de privacidad | Igual a la de autenticación |

Desde la raíz del ETL: `data/start_agents.bat` inicia todos los agentes en
ventanas independientes. Para detener:
`data/stop_agents.bat`. Consulta de prueba: `python -B data/verify_agents.py --solo huawei-dorado-01`.

El ETL identifica este storage Huawei, sus discos, controladoras, memoria por
controladora, fuentes y puertos FC. Puede registrarlo, actualizarlo y guardar
IOPS y latencia.
