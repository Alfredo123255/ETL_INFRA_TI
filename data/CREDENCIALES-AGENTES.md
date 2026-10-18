# Credenciales de los agentes SNMP simulados

Estos valores corresponden **solo a los simuladores locales de laboratorio** en `data/`. No son usuarios ni contraseñas de PostgreSQL, del backend ni de la API ETL.

Todos usan **SNMPv3**, autenticación **SHA**, privacidad **AES** y contexto SNMP `public`. En el formulario «Registrar por SNMP» ingresa el destino, usuario y **clave de autenticación**; la clave de privacidad se resuelve internamente. La columna de privacidad sirve para una consulta SNMPv3 directa.

| Equipo | Tipo | IP y puerto UDP | Usuario SNMPv3 | Clave de autenticación | Clave de privacidad |
| --- | --- | --- | --- | --- | --- |
| `hpe-dl380-01` | Servidor rack | `127.0.0.11:16100` | `HPE` | `Admin@9000` | `Enterprise` |
| `hpe-dl360-01` | Servidor rack | `127.0.0.12:16200` | `HPE` | `Enterprise` | `Enterprise` |
| `hpe-bl460c-01` | Servidor blade | `127.0.0.13:16400` | `HPE` | `Enterprise` | `Enterprise` |
| `hpe-bl460c-02` | Servidor blade | `127.0.0.14:16500` | `HPE` | `Enterprise` | `Enterprise` |
| `hpe-bl460c-03` | Servidor blade | `127.0.0.16:16900` | `HPE` | `Enterprise` | `Enterprise` |
| `hpe-c7000-01` | Chasis blade | `127.0.0.15:16300` | `HPE` | `Enterprise` | `Enterprise` |
| `hpe-storage-fc-01` | Storage | `127.0.0.30:16700` | `HPE` | `Enterprise` | `Enterprise` |
| `hpe-storage-fc-02` | Storage | `127.0.0.31:16800` | `HPE` | `Enterprise` | `Enterprise` |
| `aruba-cx-sw01` | Switch Aruba | `127.0.0.20:16600` | `HPE` | `Enterprise` | `Enterprise` |
| `huawei-2288h-v5-01` | Servidor Huawei | `127.0.0.40:17000` | `Administrator` | `Admin@9000` | `Admin@9000` |
| `huawei-ch121-v5-01` | Blade Huawei | `127.0.0.41:17100` | `Administrator` | `Admin@9000` | `Admin@9000` |
| `huawei-e9000-01` | Chasis Huawei | `127.0.0.42:17200` | `Administrator` | `Admin@9000` | `Admin@9000` |
| `huawei-dorado-01` | Storage Huawei | `127.0.0.43:17300` | `Administrator` | `Admin@9000` | `Admin@9000` |
| `huawei-2288h-v5-02` | Servidor Huawei | `127.0.0.44:17400` | `Administrator` | `Admin@9000` | `Admin@9000` |
| `huawei-ch121-v5-02` | Blade Huawei | `127.0.0.45:17500` | `Administrator` | `Admin@9000` | `Admin@9000` |
| `huawei-e9000-02` | Chasis Huawei | `127.0.0.46:17600` | `Administrator` | `Admin@9000` | `Admin@9000` |
| `huawei-dorado-02` | Storage Huawei | `127.0.0.47:17700` | `Administrator` | `Admin@9000` | `Admin@9000` |

## Uso desde el frontend

1. Inicia el agente correspondiente.
2. En «Registrar por SNMP», escribe la **IP con puerto**, el **usuario** y la **clave de autenticación** de su fila. Repite esa clave en «Confirmar clave».
3. Pulsa «Probar conexión». Después selecciona un clúster y registra el activo.

La clave del `hpe-dl380-01` en esta tabla es `Admin@9000`, que apareció en la configuración de arranque posterior al cambio de contraseña de las pruebas. Si el proceso del agente estaba encendido antes de ese cambio, reinícialo para que use esa clave.
