# Credenciales de los agentes SNMP simulados

Estos valores corresponden **solo a los simuladores locales de laboratorio** en `data/`. No son usuarios ni contraseñas de PostgreSQL, del backend ni de la API ETL.

Todos usan **SNMPv3**, autenticación **SHA**, privacidad **AES** y contexto SNMP `public`. En el formulario «Registrar por SNMP» ingresa el destino, usuario y **clave de autenticación**; la clave de privacidad se resuelve internamente. La columna de privacidad sirve para una consulta SNMPv3 directa.

| Equipo | Tipo | IP y puerto UDP | Usuario SNMPv3 | Clave de autenticación | Clave de privacidad |
| --- | --- | --- | --- | --- | --- |
| `hpe-dl380-01` | Servidor rack | `127.0.0.11:16100` | `monitor_dl380` | `Admin@9000` | `GpoJkRAhPOZg3vA4qHyT` |
| `hpe-dl360-01` | Servidor rack | `127.0.0.12:16200` | `monitor_dl360` | `3nRFCWnSuDougjTVD3SV` | `Wru30SG1uouCjtcd5h7P` |
| `hpe-bl460c-01` | Servidor blade | `127.0.0.13:16400` | `monitor_bl460c01` | `Yb2QzP9mLxT4wVh8Kd3R` | `Ft6NcE1oRgJ5sWp2Ux9M` |
| `hpe-bl460c-02` | Servidor blade | `127.0.0.14:16500` | `monitor_bl460c02` | `Ht4RxQ8kMbZ3vNp6Ld1J` | `Sc9WjE2yTfL7uKq4Gz5V` |
| `hpe-bl460c-03` | Servidor blade | `127.0.0.16:16900` | `monitor_bl460c03` | `Fq8DzT4mWpK7vN2sRb6C` | `Jr5XeA9pLcQ2tW8mHk4V` |
| `hpe-c7000-01` | Chasis blade | `127.0.0.15:16300` | `monitor_c7000` | `cy8EcO4BePPAN9Os5zts` | `NR2yILtdOtWShA70stgf` |
| `hpe-storage-fc-01` | Storage | `127.0.0.30:16700` | `monitor_storagefc01` | `RcVQ87sKGKNAXteaPhvF` | `87KIBACIxZCukpKjai0Z` |
| `hpe-storage-fc-02` | Storage | `127.0.0.31:16800` | `monitor_storagefc02` | `SMkMLpmciBdaLR9pfDux` | `2VcFacU3YHQ1CqwgAg7D` |
| `aruba-cx-sw01` | Switch Aruba | `127.0.0.20:16600` | `monitor_sw01` | `2JePukZ17WBQg10i3J3U` | `ZynkEa6RTaPcFsqG1Oc5` |
| `huawei-2288h-v5-01` | Servidor Huawei | `127.0.0.40:17000` | `monitor_hw2288` | `Hw2288Lab2026Auth` | `Hw2288Lab2026Auth` |
| `huawei-ch121-v5-01` | Blade Huawei | `127.0.0.41:17100` | `monitor_hwch121` | `HwCH121Lab2026Auth` | `HwCH121Lab2026Auth` |
| `huawei-e9000-01` | Chasis Huawei | `127.0.0.42:17200` | `monitor_hwe9000` | `HwE9000Lab2026Auth` | `HwE9000Lab2026Auth` |
| `huawei-dorado-01` | Storage Huawei | `127.0.0.43:17300` | `monitor_hwdorado` | `HwDoradoLab2026Auth` | `HwDoradoLab2026Auth` |
| `huawei-2288h-v5-02` | Servidor Huawei | `127.0.0.44:17400` | `monitor_hw2288_02` | `Hw2288Lab2026Auth02` | `Hw2288Lab2026Auth02` |
| `huawei-ch121-v5-02` | Blade Huawei | `127.0.0.45:17500` | `monitor_hwch121_02` | `HwCH121Lab2026Auth02` | `HwCH121Lab2026Auth02` |
| `huawei-e9000-02` | Chasis Huawei | `127.0.0.46:17600` | `monitor_hwe9000_02` | `HwE9000Lab2026Auth02` | `HwE9000Lab2026Auth02` |
| `huawei-dorado-02` | Storage Huawei | `127.0.0.47:17700` | `monitor_hwdorado_02` | `HwDoradoLab2026Auth02` | `HwDoradoLab2026Auth02` |

## Uso desde el frontend

1. Inicia el agente correspondiente.
2. En «Registrar por SNMP», escribe la **IP con puerto**, el **usuario** y la **clave de autenticación** de su fila. Repite esa clave en «Confirmar clave».
3. Pulsa «Probar conexión». Después selecciona un clúster y registra el activo.

La clave del `hpe-dl380-01` en esta tabla es `Admin@9000`, que apareció en la configuración de arranque posterior al cambio de contraseña de las pruebas. Si el proceso del agente estaba encendido antes de ese cambio, reinícialo para que use esa clave.
