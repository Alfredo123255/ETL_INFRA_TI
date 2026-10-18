# ETL de infraestructura TI — entorno SNMP simulado

Este repositorio incluye diecisiete agentes SNMPv3 simulados: nueve HPE/Aruba y ocho Huawei.
El ETL crea activos HPE/Aruba y Huawei en PostgreSQL; los perfiles Huawei cubren
servidor rack, blade, chasis E9000 y storage OceanStor Dorado. La API corre
separada del backend Spring Boot.

## Arranque local completo (Windows)

Usa PowerShell en `C:\INGESOFT\ETL_INFRA_TI`. Requiere Python con las dependencias de
`requirements.txt`, PostgreSQL, Java 21 para el backend y Node.js si también quieres el frontend.
Cada bloque de arranque se ejecuta en una terminal distinta.

1. **Preparar Python y PostgreSQL** (solo la primera vez):

   ```powershell
   cd C:\INGESOFT\ETL_INFRA_TI
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Get-Service 'postgresql*'
   # Solo si el servicio está detenido; puede requerir PowerShell como administrador:
   if ((Get-Service postgresql-x64-17).Status -ne "Running") { Start-Service postgresql-x64-17 }
   psql -h 127.0.0.1 -U postgres -d postgres -f .\migrations\001_monitoreo_clave_privacidad.sql
   ```

   El esquema de activos y las tablas `monitoreo_snmp`, `clusters` y `datacenters`
   deben existir antes de ejecutar esa migración. Si `psql` no está en `PATH`, usa
   `C:\Program Files\PostgreSQL\17\bin\psql.exe`. La migración agrega
   `clave_privacidad` para agentes con claves SNMPv3 diferentes; se puede ejecutar
   de nuevo sin duplicar la columna.

2. **Iniciar los diecisiete agentes SNMP**:

   ```powershell
   cd C:\INGESOFT\ETL_INFRA_TI
   .\.venv\Scripts\Activate.ps1
   .\data\start_agents.bat
   .\.venv\Scripts\python.exe -B .\data\verify_agents.py
   ```

   El iniciador incluye DL380, DL360, tres blades, chasis c7000, switch Aruba, dos
   storage HPE y dos instancias de cada perfil Huawei: 2288H, CH121, E9000 y OceanStor Dorado. Cada agente abre
   una ventana; la verificación confirma qué agente responde. Las credenciales y destinos
   simulados están en `data/<agente>/README.md`. En este equipo el iniciador usa
   el Python de Miniconda (`%USERPROFILE%\miniconda3\python.exe`), donde está
   instalado `snmpsim`; puede ejecutarse aunque `.venv` esté activado.

3. **Configurar y arrancar la API ETL**:

   ```powershell
   cd C:\INGESOFT\ETL_INFRA_TI
   Copy-Item .env.example .env
   notepad .env
   .\.venv\Scripts\python.exe -B -m api.main
   ```

   En `.env`, configura al menos estos valores con tu clave API y la contraseña
   de tu PostgreSQL local:

   ```dotenv
   ETL_API_KEY=<tu-clave-api>
   DATABASE_URL=postgresql://postgres:<tu-clave-postgres>@127.0.0.1:5432/postgres
   SNMP_CONTEXT_NAME=public
   SNMP_REDES_PERMITIDAS=127.0.0.0/8,::1/128
   API_HOST=127.0.0.1
   API_PORT=8001
   API_DOCS=1
   ```

   Comprueba `http://127.0.0.1:8001/docs`. Para crear un activo envía
   `X-API-Key` y `Content-Type: application/json` a
   `POST http://127.0.0.1:8001/api/etl/crear-activo`:

   ```json
   {"conexion_id": 7, "cluster_id": "CLUSTER-LAB-LOCAL"}
   ```

   Los IDs del ejemplo corresponden a esta base local: conexión 7 = switch Aruba.
   En otra base, consulta los IDs de `monitoreo_snmp` y el nombre de `clusters`.
   La creación detecta el tipo por SNMP, guarda los componentes y vincula el ID
   del activo a la conexión. La conexión debe tener IP, usuario y claves válidas.

4. **Iniciar el backend Spring Boot**, en otra terminal:

   ```powershell
   cd C:\INGESOFT\Backend-SI-INFRA-TI\backend-infra-ti
   .\mvnw.cmd spring-boot:run '-Dspring-boot.run.arguments=--server.port=8080'
   ```

   Comprueba `http://127.0.0.1:8080/api/servidores`. Este backend usa todavía
   los repositorios Excel de su proyecto; arrancarlo no hace que muestre los
   activos que el ETL acaba de guardar en PostgreSQL.

5. **Opcional: iniciar el frontend**, en otra terminal:

   ```powershell
   cd C:\INGESOFT\Frontend-SI-INFRA-TI\Frontend-SI-INFRA-TI
   npm install
   npm run dev -- --host 127.0.0.1 --port 4200
   ```

   Abre `http://127.0.0.1:4200/`. Si las dependencias ya están instaladas,
   omite `npm install`.

En esta computadora también existe
`C:\Users\jenny\OneDrive\Escritorio\Tesis\iniciar_sistema_local.py`, que arranca
API, programador de monitoreo, backend y frontend y genera una colección Postman.
Para usarlo en esta instalación, después de iniciar los agentes, ejecuta:

```powershell
cd C:\Users\jenny\OneDrive\Escritorio\Tesis
$pgSecret = Read-Host "Contraseña de PostgreSQL" -AsSecureString
$env:PGPASSWORD = [System.Net.NetworkCredential]::new("", $pgSecret).Password
C:\INGESOFT\ETL_INFRA_TI\.venv\Scripts\python.exe -B .\iniciar_sistema_local.py
Remove-Item Env:PGPASSWORD
```

La colección queda en
`C:\Users\jenny\OneDrive\Escritorio\Tesis\outputs\sistema_local\Prueba_local.postman_collection.json`.

## Monitoreo periódico de activos ya registrados

El alta por Postman vincula `monitoreo_snmp.activo_id`. Para iniciar el ETL periódico,
ejecuta en otra terminal, con el mismo `.env` que utiliza la API:

```powershell
cd C:\INGESOFT\ETL_INFRA_TI
.\.venv\Scripts\python.exe -B -m etl.programador
```

`frecuencia_actualizacion` se interpreta en **segundos** (por ejemplo, `60` = un minuto).
En cada ciclo el programador relee las conexiones vinculadas, su frecuencia y sus
credenciales; los cambios en la BD se aplican en la próxima consulta. Solo se consultan
las conexiones en `Activo` o `Sin conexión` (estas últimas se reintentan). Las conexiones
en `Inactivo`, sin activo vinculado o con frecuencia menor o igual a cero no se monitorean. Un bloqueo
de PostgreSQL impide que dos programadores periódicos corran al mismo tiempo.

Para probar una sola iteración sin mantener el proceso abierto:

```powershell
.\.venv\Scripts\python.exe -B -m etl.programador --una-vez --conexion-id 7
```

En una lectura exitosa, el ETL compara los datos SNMP con `activo`, su subtipo y sus
componentes. Actualiza únicamente los valores cambiados, conserva los campos
administrativos del front, añade las métricas a `metrica_historica` y escribe
`activo.ultima_actualizacion` en cada lectura exitosa, incluso sin otros cambios.
Esta columna y `monitoreo_snmp.fecha_ultima_actualizacion` guardan la misma marca
UTC de la consulta exitosa. Los cambios de `estado_operativo` y de `estado` en
componentes generan filas en `historico_estado`; los componentes nuevos o que dejan
de reportarse también generan un evento. Una pieza reemplazable ausente se elimina físicamente, tras confirmar la lectura;
el evento de presencia se conserva. Los puertos y slots conservan sus filas,
incluso apagados o libres. Si falla SNMP
y la conexión estaba `Activo`, pasa a `Sin conexión` y se registra el evento; al
recuperarse vuelve a `Activo` y se registra otro. Los fallos repetidos no duplican eventos. Si falla
SNMP, no se modifican ni `activo.ultima_actualizacion` ni
`monitoreo_snmp.fecha_ultima_actualizacion`: ambas conservan la última lectura
exitosa. La hora del fallo se guarda únicamente en el evento de estado.

## Datos simulados

Los archivos `data/<agente>/public.snmprec` contienen las respuestas SNMP de los diecisiete
agentes. Los MIB y los documentos de mapeo de OID están en `mibs/`; los Huawei en
[`mibs/huawei/MAPEO-HUAWEI.md`](mibs/huawei/MAPEO-HUAWEI.md). Para cambiar
una simulación, edita su archivo de datos y ejecuta las dos verificaciones de la
sección siguiente antes de usarla desde la API.

## Validar un `.snmprec` antes de hacer commit

Después de editar a mano cualquier `data/<agente>/public.snmprec`, correr el validador estático
(no levanta ningún agente, revisa formato, etiquetas, rangos de valor, orden ascendente de OID y
duplicados) antes de commitear:
```
python data/validar_snmprec.py
```
Termina con código de salida distinto de cero si encuentra algún problema (archivo, línea y
motivo quedan impresos). Ver también `data/verify_agents.py`, que además de esto hace un walk
SNMP completo contra cada agente ya levantado y lo compara contra su `.snmprec`.

## Estructura del ETL y la API

`etl/extraccion/` contiene los perfiles SNMP de servidor, switch, storage y
chasis; `etl/normalizacion/` convierte sus valores a las tablas del esquema.
`etl/ciclo.py` detecta el tipo de equipo, `etl/repositorio.py` guarda el subtipo
y componentes, y `etl/carga.py` vincula el activo con `monitoreo_snmp` dentro
de una transacción. `api/main.py` expone las rutas de prueba y creación.

## API de validación de conexión

`POST /api/etl/probar-conexion` prueba SNMPv3 sin crear un activo. Recibe IP,
usuario y clave de autenticación, más una clave de privacidad opcional.
`POST /api/etl/crear-activo` usa una conexión y un clúster ya guardados en la
base; su contrato está documentado al final de este README.

### Instalación y configuración

Desde la raíz del repositorio, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Editar `.env` y reemplazar `ETL_API_KEY` por una clave propia. Si falta o está vacía, la API
falla al cargar y no arranca. No se registra el cuerpo de las solicitudes ni se devuelve el
texto arbitrario de excepciones de SNMP.

| Variable | Valor predeterminado / uso |
|---|---|
| ETL_API_KEY | Obligatoria; el llamador la envía en X-API-Key. |
| SNMP_CONTEXT_NAME | Vacío para equipos reales; usar public con los simuladores. |
| SNMP_TIMEOUT | 3 segundos por intento. |
| SNMP_RETRIES | 1 reintento; un timeout suele tardar más de 6 segundos en total. |
| API_HOST | 127.0.0.1. |
| API_PORT | 8001. |
| API_DOCS | 0; 1 habilita /docs y /openapi.json. |
| SNMP_REDES_PERMITIDAS | Vacío no restringe. Ejemplo: 127.0.0.0/8,::1/128. |

La API permite cinco pruebas simultáneas **por proceso**. Ejecutar un único worker para
mantener el límite global en cinco. No tiene CORS.

Arranque solicitado:

```powershell
uvicorn api.main:app --host 127.0.0.1 --port 8001
```

Alternativa que utiliza `API_HOST` y `API_PORT` del archivo `.env`:

```powershell
python -m api.main
```

Los argumentos `--host` y `--port` de Uvicorn son explícitos; Uvicorn no interpreta por sí
solo las variables personalizadas `API_HOST` y `API_PORT`.

### Agentes simulados

Para los diecisiete agentes usa el comando del paso 2 de «Arranque local completo».
`data/start_agents.bat` inicia los diecisiete en ventanas visibles;
`data/stop_agents.bat` los detiene, incluido el blade 3.
El wrapper `data/run_responder.py` carga solamente la variación `numeric`,
que es la única usada por los archivos `.snmprec`; los módulos opcionales
Redis y SQL no se inicializan.
Para verificar solo los nuevos Huawei: `python -B data/verify_agents.py --solo huawei-2288h-v5-02 huawei-ch121-v5-02 huawei-e9000-02 huawei-dorado-02`.

### Llamada desde PowerShell

El ejemplo pide las claves sin escribirlas en el historial de comandos. Usar las credenciales
documentadas en [el README del DL380](data/hpe-dl380-01/README.md). El endpoint no las guarda.

```powershell
$apiKey = Read-Host "ETL_API_KEY configurada en la API" -AsSecureString
$authKey = Read-Host "Clave de autenticación SNMP del DL380" -AsSecureString
$privKey = Read-Host "Clave de privacidad SNMP del DL380" -AsSecureString

$headers = @{
    "X-API-Key" = [System.Net.NetworkCredential]::new("", $apiKey).Password
}
$body = @{
    ip_gestion = "127.0.0.11:16100"
    usuario = "monitor_dl380"
    clave = [System.Net.NetworkCredential]::new("", $authKey).Password
    clave_privacidad = [System.Net.NetworkCredential]::new("", $privKey).Password
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/api/etl/probar-conexion" `
    -Headers $headers -ContentType "application/json" -Body $body
```

Se acepta IP o nombre DNS, con puerto opcional (161 por defecto). Para IPv6 con puerto,
usar `[::1]:16100`; una IPv6 sin corchetes se interpreta completa, con puerto 161.
No se aceptan URL, rutas, puertos fuera de 1–65535 ni campos vacíos.
La privacidad usa la clave de autenticación si `clave_privacidad` falta o es null.

Si se configuraron redes permitidas, se comprueban todas las direcciones resueltas del nombre
DNS; un destino con direcciones fuera de las redes se rechaza con 422. Se consulta la IP
validada, sin resolver otra vez el nombre. Un fallo DNS responde 200 con fallo de conexión.

### Respuestas y detección

- 200: resultado de la consulta; `ok=true` o `ok=false`.
- 401: X-API-Key ausente o incorrecta, comparada con `hmac.compare_digest`.
- 422: cuerpo inválido o destino no permitido. Solo expone campo y motivo; no valores recibidos.
- Claves modeladas con SecretStr; mensajes de fallo fijos en español, sin claves ni usuario.
- El log de la prueba solo incluye host, puerto, usuario, resultado y milisegundos.
- El tiempo incluye espera por el semáforo, resolución, GET y detección.

GET inicial: `sysDescr.0` (`1.3.6.1.2.1.1.1.0`), `sysObjectID.0`
(`1.3.6.1.2.1.1.2.0`) y `sysName.0` (`1.3.6.1.2.1.1.5.0`).
SNMPv3 authPriv, SHA/AES; motor independiente por petición y cierre en `finally`,
incluyendo cancelaciones.

Fabricante: diccionario central en [etl/detector.py](etl/detector.py), basado en el enterprise
de sysObjectID; fabricante desconocido produce null.

Orden de detección, comprobando con GETNEXT que el resultado está estrictamente bajo el
subárbol esperado y no es EndOfMibView/NoSuchObject/NoSuchInstance:

1. sysObjectID de enterprise 47196 y subárbol `1.3.6.1.4.1.47196`: SWITCH.
2. Subárbol `1.3.6.1.4.1.232.22`: CHASIS.
3. Subárbol `1.3.6.1.4.1.232.16`: STORAGE.
4. Subárbol `1.3.6.1.4.1.232.11`: SERVIDOR.
5. Huawei OceanStor (`34774`) con `1.3.6.1.4.1.34774.4.1.23`: STORAGE.
6. Huawei (`2011`) con `1.3.6.1.4.1.2011.2.82.1.82.2`: CHASIS;
   con `1.3.6.1.4.1.2011.2.235.1.1`: SERVIDOR.
7. Sin evidencia o fallo de detección: DESCONOCIDO, manteniendo `ok=true` si el GET inicial funcionó.

El orden evita clasificar el storage como servidor por sus OID compartidos.
Después de detectar servidor Huawei, el perfil iBMC distingue blade de rack
mediante ranura y serie de chasis; no usa usuario ni IP para clasificar.
Las bases se contrastaron con los MAPEO y los `public.snmprec`.

### Verificación realizada en Windows

Entorno de prueba: Python 3.14.6, pysnmp 6.2.6, snmpsim 1.1.7, FastAPI 0.142.1,
Uvicorn 0.54.0. El cliente se crea dentro de la función asíncrona, con un bucle activo;
no fue necesario cambiar la política de eventos de Windows. Los agentes siguen usando
su wrapper existente `data/run_responder.py`.

Resultados de integración con SNMP_TIMEOUT=3 y SNMP_RETRIES=1
(los tiempos varían entre ejecuciones):

| Agente | ok | fabricante | tipo_detectado | milisegundos |
|---|---|---|---|---:|
| hpe-dl380-01 | true | HPE | SERVIDOR | 354 |
| hpe-dl360-01 | true | HPE | SERVIDOR | 259 |
| hpe-bl460c-01 | true | HPE | SERVIDOR | 321 |
| hpe-bl460c-02 | true | HPE | SERVIDOR | 301 |
| hpe-c7000-01 | true | HPE | CHASIS | 225 |
| hpe-storage-fc-01 | true | HPE | STORAGE | 275 |
| hpe-storage-fc-02 | true | HPE | STORAGE | 259 |
| aruba-cx-sw01 | true | HPE Aruba Networking | SWITCH | 233 |

Textos reales obtenidos directamente de `errorIndication` de pysnmp al probar el DL380:

| Caso | Clase de pysnmp | Texto real | error_tipo | ms de la API |
|---|---|---|---|---:|
| Destino UDP sin respuesta SNMP | RequestTimedOut | No SNMP response received before timeout | timeout | 6799 |
| Usuario incorrecto | UnknownUserName | Unknown USM user | usuario_desconocido | 164 |
| Clave de autenticación incorrecta | WrongDigest | Wrong SNMP PDU digest | clave_autenticacion | 183 |
| Clave de privacidad incorrecta | DecryptionError | Ciphering services not available or ciphertext is broken | clave_privacidad | 228 |

En estos agentes los cuatro casos **sí fueron distinguibles**. Un equipo real puede descartar
silenciosamente las solicitudes inválidas: si devuelve timeout, se informa timeout, sin
inventar una causa. También se mapea Unsupported SNMP security level a nivel_seguridad;
este último se comprobó con pruebas unitarias, no provocándolo en el simulador.

Prueba adicional con Uvicorn, por HTTP real en 127.0.0.1:8001:

```json
{"ok":true,"descripcion":"HPE ProLiant DL380 Gen10","sys_object_id":"1.3.6.1.4.1.232.9.4.10","sys_name":"hpe-dl380-01","fabricante":"HPE","tipo_detectado":"SERVIDOR","milisegundos":332}
```

También se verificó HTTP 401 sin X-API-Key, HTTP 422 sin secretos y /docs desactivado.

### Ejecutar pruebas

```powershell
python -m pytest -q -m "not integracion"
python -m pytest -q -s
```

Las pruebas de integración leen destinos y credenciales de cada `data/*/README.md`.
Solo omiten un agente si no responde (timeout); errores de autenticación y tipos inesperados
hacen fallar la prueba. El caso sin respuesta reserva temporalmente un puerto UDP sin
respondedor SNMP para evitar conflictos de asignación.

Resultado de la ejecución completa:

```text
85 passed, 80 warnings in 12.38s
```

Sin pruebas omitidas. Los avisos corresponden a deprecaciones de dependencias
(pysmi, cryptography y TestClient/httpx) y un aviso de caché de pytest del entorno de ejecución;
no fueron fallos de conexión ni de las aserciones.

## Registro inicial de servidores, switch Aruba, storage y chasis HPE

Los cuatro tipos de activo simulados tienen extracción, normalización y registro
inicial en PostgreSQL mediante
`POST /api/etl/crear-activo`. La ruta de prueba de conexión conserva su contrato.

- `etl/oids/servidor.py`: perfil HPE con escalares, columnas y enumeración de
  modelos de controladora transcrita de CPQIDA-MIB.
- `etl/snmp_cliente.py`: `ConexionSNMP` y `SesionSNMP`, con GET y recorridos
  GETBULK delimitados al subárbol; cierre del motor incluso al cancelar.
- `etl/extraccion/servidor.py`: `extraer_servidor_hpe(conexion)` devuelve valores
  ASN.1 por OID completo para HPE.
- `etl/extraccion/{servidor,chasis,storage}.py` y
  `etl/normalizacion/{servidor,chasis,storage}.py`: perfiles HPE y Huawei por
  tipo de activo. El chasis cruza la serie FRU del blade con el mismo datacenter.
- `etl/normalizacion/servidor.py`: produce `activo`, `servidor`, `componentes`,
  `mediciones` y el texto original de `ubicacion_snmp`, con nombres del esquema.
- `etl/ciclo.py`: `preparar_registro_activo` detecta el tipo por SNMP y selecciona
  el perfil de extracción y normalización correspondiente.
- `etl/db.py`, `etl/repositorio.py` y `etl/carga.py`: conexión, SQL parametrizado y
  transacción única para registrar activo, subtipo, componentes, puertos, métricas
  y el vínculo con la conexión SNMP.
- `etl/metricas.py`: prepara las mediciones para `metrica_historica`.

`cpuTotalGhz` queda a cargo del backend. `cpu_uso_ghz` y `ram_uso_gb` se devuelven
como mediciones, con los nombres que consume el backend y usa la migración de
Excel. La base para calcular el uso de CPU es la suma de velocidad en GHz ×
cantidad de núcleos de cada CPU; sobre esa capacidad se aplica el porcentaje
SNMP (promedio de las filas de utilización válidas). Si faltan velocidades o
núcleos válidos, no se genera una métrica de uso de CPU parcial.
`serie` de componentes se normaliza a `numero_serial`; la serie
del activo es `numero_serie`. `ultima_actualizacion` se asigna al guardar el
activo con fecha y hora UTC. Los campos sin fuente quedan
vacíos; la revisión de arquitectura de CPU no se interpreta como familia.

El datacenter del registro se obtiene del clúster existente indicado en la solicitud.
El modelo distingue los servidores rack de los blade. Los componentes compartidos
del chasis no se duplican. Si el chasis y el blade están en el mismo clúster,
sus slots se vinculan por hostname al crear el segundo de los dos activos.

### Registro inicial por API

Configurar `DATABASE_URL` y, opcionalmente, `DB_TIMEOUT` en `.env`. La prueba de
conexión no requiere estas variables. Instalar las dependencias actualizadas de
`requirements.txt`, incluido el controlador `psycopg2-binary`.

Las instalaciones nuevas deben partir de `schema.sql`, exportado del esquema
vigente: incluye `clave_privacidad VARCHAR(255)` y `activo.ultima_actualizacion`
como `TIMESTAMP WITHOUT TIME ZONE`. Las instalaciones antiguas deben revisar
`migrations/001_monitoreo_clave_privacidad.sql` y
`migrations/002_activo_ultima_actualizacion_hora.sql` antes del despliegue.
El ETL no aplica DDL automáticamente. `python -m etl.esquema` comprueba el contrato
y el programador se detiene con un mensaje claro si falta alguna columna o tipo. Debe existir el datacenter y el clúster antes de crear el activo.

Enviar `X-API-Key` y este cuerpo a `POST /api/etl/crear-activo`:

```json
{
  "conexion_id": 1,
  "cluster_id": "CLUSTER-LAB-LOCAL"
}
```

`conexion_id` es el ID entero positivo de una fila existente de `monitoreo_snmp`.
`cluster_id` corresponde a `clusters.nombre`, la clave primaria textual del esquema;
no existe un ID numérico de clúster. El tipo de equipo se detecta por SNMP; para servidores HPE, RACKEABLE o BLADE
se infiere del modelo. No se reciben IP, usuario, contraseña ni ubicación en esta petición.
El ETL obtiene IP y credenciales de la conexión. `clave` se usa para autenticación
SNMPv3; `clave_privacidad` para privacidad. Cuando la segunda es NULL se utiliza
`clave` para ambas. El datacenter proviene de `clusters.datacenter`.

Se admiten los perfiles simulados HPE ProLiant (rack y blade), ArubaOS-CX,
HPE StorageWorks con arreglo Fibre Channel, HPE BladeSystem c7000, Huawei
FusionServer/CH121, E9000 y OceanStor Dorado. Equipos
sin un perfil compatible se rechazan.

El proceso crea el modelo en `modelos` si no existe, inserta `activo` y su
subtipo (`servidor`, `switch`, `storage` o `chasis_blade`), además de los
componentes y métricas disponibles según el perfil. El switch guarda 52 puertos
físicos; los storage guardan discos del arreglo FC y componentes del host
administrador; el chasis guarda slots, ventiladores, fuentes e interconexiones.
Si falla cualquier escritura, se deshace toda la transacción, incluido un modelo
nuevo. El registro inicial no actualiza activos existentes ni genera duplicados.

Dentro de la misma transacción se asigna `activo.cluster` y se actualiza la conexión
existente: `monitoreo_snmp.activo_id`, estado `Activo` y fecha de última actualización.
No se crea una segunda conexión ni se cambia su frecuencia. Antes de guardar se
bloquean y revalidan conexión y clúster; una vinculación previa o un cambio concurrente
impiden la creación. Si falla el vínculo, también se revierten activo, componentes y
métricas.

También en esa transacción se insertan eventos iniciales en `historico_estado`, con la
misma marca de tiempo UTC de las métricas (`fecha_cambio` se pasa explícita):

| `campo` | `valor_nuevo` | `descripcion` | Cuándo |
|---|---|---|---|
| `estado_operativo` | el estado real de la ficha (`Encendido`, `Apagado` o `Degradado`) | `Estado inicial al registrar el activo` | siempre |
| `estado_conexion` | `Activo` | `Conexión SNMP vinculada al registrar el activo` | solo si hay conexión vinculada, tras `vincular()` |

Los valores de `campo` son exactamente `estado_operativo` y `estado_conexion` (los nombres
de las columnas que cambian); el futuro ciclo automático debe reutilizarlos
(`etl/repositorio.py`) para comparar y registrar cambios. El alta no registra eventos de
componentes (discos, puertos, fuentes, etc.): los generará el ciclo de monitoreo cuando
detecte un cambio. Si el alta falla o se revierte, no queda ningún evento. La respuesta 201
incluye `eventos_registrados` (2 con conexión vinculada, 1 sin ella).
Los activos creados con el contrato anterior no se vinculan retroactivamente.
Los campos administrativos sin OID, como `switch.tipo_red`,
`switch.modo_operacion` y `storage.iops` nominal, quedan NULL para que los
complete el front. El valor de capacidad usada del storage depende del bloque
Nimble prestado en la simulación; puede quedar NULL en hardware que no lo exponga.

Respuestas:

- 201: activo creado; devuelve `activo_id`, `conexion_id`, `cluster_id`, identidad, `estado_operativo`, ubicación y cantidades guardadas. El estado se obtiene por SNMP y no se envía en el body.
- 401: clave de API ausente o incorrecta.
- 404: conexión o clúster inexistente.
- 409: serie/hostname duplicado, conexión ya vinculada o referencias modificadas durante la consulta.
- 422: solicitud, ficha o datacenter inválidos, o perfil no implementado.
- 502/504: fallo de comunicación SNMP o tiempo de espera agotado.
- 503: PostgreSQL no configurado, no disponible o fallo de persistencia.

Las mediciones se almacenan en UTC en el TIMESTAMP sin zona de `fecha_medicion`;
`activo.ultima_actualizacion` conserva fecha y hora UTC de la última lectura SNMP
exitosa, igual que `monitoreo_snmp.fecha_ultima_actualizacion`. El frontend la
muestra en hora de Lima. Una consulta SNMP fallida no modifica ninguna de las dos.

Antes de iniciar esta versión del ETL y del backend, aplica una vez
`migrations/002_activo_ultima_actualizacion_hora.sql` a la base configurada en
`DATABASE_URL`. La migración amplía `activo.ultima_actualizacion` de `DATE` a
`TIMESTAMP`; recupera la hora de `monitoreo_snmp` para activos vinculados. Para
activos antiguos sin esa marca, conserva el día a las 00:00 UTC porque la hora
original no se almacenó.

Verificación de esta etapa:

```powershell
python -m pytest -q tests/unitarios tests/integracion/test_servidor.py
```

Las pruebas de integración de servidor levantan simuladores temporales en
puertos locales disponibles y los cierran al terminar. Requieren `snmpsim`.
Las pruebas de persistencia usan conexiones de prueba controladas para verificar
SQL parametrizado, relaciones, commit y rollback. La creación y vinculación atómicas se verificaron además contra PostgreSQL local
en un esquema aislado, incluyendo rollback ante fallo del vínculo y rechazo de repetición.

## Reconciliación de componentes durante el monitoreo

Las piezas reemplazables que dejan de aparecer en una lectura con elementos
se eliminan físicamente de su tabla. Las piezas nuevas se insertan, y una pieza
retirada que reaparece se registra de nuevo. Cada incorporación o retiro confirmado
registra un evento en `historico_estado` con campo `presencia` y valor `Agregado`
o `Retirado`, tipo de componente, identificador y fecha. El evento de retiro se
conserva aunque la fila del componente se elimine. La escritura y el evento
comparten la misma transacción: si falla el ciclo, ambos se revierten. Las lecturas
posteriores sin cambios no duplican los eventos. Se mantienen los eventos de
estado inicial y de salud; Baja sigue siendo exclusiva de activos.

Una tabla completamente vacía con componentes registrados se conserva en la
primera lectura. `LECTURAS_VACIAS_PARA_BAJA` configura cuántas lecturas vacías
consecutivas se requieren para confirmar el retiro (por defecto, 2). Una lectura
con elementos reinicia la confirmación, incluso cuando los datos son idénticos.
El contador se guarda en memoria y solo avanza al confirmar la transacción.
Al reiniciar el programador comienza otra vez la confirmación conservadora.
Los marcadores técnicos antiguos se ocultan en la consulta del historial; no se borran.
No se crean tablas ni se modifica el esquema. El resultado incluye `tablas_omitidas`.

Los puertos de switch, puertos de NIC y slots del chasis conservan sus filas,
incluidos puertos apagados y slots libres. La retirada confirmada de una NIC
elimina primero sus puertos asociados. Los slots que se liberan conservan la
fila y desvinculan el blade; una primera lectura vacía conserva esos vínculos.
Los puertos y slots no generan eventos de incorporación o retiro de piezas:
conservan su estructura y sus eventos de estado. Completar el serial de una NIC
existente tampoco genera una incorporación y un retiro artificiales.

Las pruebas de `tests/integracion/test_reconciliacion_componentes.py` usan el
esquema existente de una base `TEST_DATABASE_URL` cuyo nombre contenga `test`,
y revierten los datos insertados por cada prueba al finalizar.


## Cifrado de credenciales SNMP

El backend escribe `clave` y `clave_privacidad` con AES-256-GCM, nonce aleatorio
de 12 bytes y autenticación separada por campo. Python descifra únicamente al
preparar una consulta SNMP. El formato compartido es `enc:v1:` seguido de Base64
URL sin relleno de nonce, texto cifrado y tag de 16 bytes. Las respuestas HTTP,
resultados y logs no incluyen las claves. El usuario SNMP se mantiene legible.

Crear una llave aleatoria de 32 bytes codificada en Base64 URL y guardarla en un
archivo externo con permisos limitados al usuario de servicio. Configurar en
backend y ETL `SNMP_CREDENTIAL_KEY_FILE` con la ruta a ese mismo archivo; para
contenedores, montarlo como secreto de solo lectura. También se admite
`SNMP_CREDENTIAL_KEY` desde el gestor de secretos. Nunca subir la llave a Git,
incluirla en una imagen ni almacenarla junto a una copia pública de la BD.

Respaldar de forma privada la llave antes de convertir datos. Con backend y
programador detenidos, ejecutar `python -m etl.migrar_credenciales` y después
`python -m etl.migrar_credenciales --verificar`; debe indicar cero pendientes.
La conversión es atómica e idempotente. No cambia tablas ni columnas. Iniciar
backend, FastAPI y programador con la misma llave. Los lectores aceptan texto
previo durante la conversión; las nuevas escrituras del backend siempre cifran.
Una llave ausente, incorrecta o un valor manipulado no produce una consulta SNMP
con el texto cifrado ni sobreescribe el inventario. El límite conservador de cada
contraseña es 158 bytes UTF-8 para respetar el VARCHAR(255) existente.

La llave permite recuperar las credenciales: conservarla y respaldarla fuera del
repositorio. Cambiarla exige descifrar con la llave anterior y volver a cifrar;
reemplazar simplemente el archivo dejaría inaccesibles las claves guardadas.
El cifrado de almacenamiento no reemplaza TLS al desplegar las APIs.

Los simuladores de este laboratorio usan HPE `HPE` / `Enterprise` (incluido Aruba)
y Huawei `Administrator` / `Admin@9000`, con la misma clave para autenticación y
privacidad. Son credenciales de demostración documentadas para este entorno.

## Lectura después de editar una conexión

Al guardar una edición validada, el backend envía un aviso PostgreSQL
`etl_actualizar_conexion` con el ID de conexión. Se entrega después del commit;
un rollback no solicita lectura. El programador lo revisa cada 2 segundos y
consulta el activo sin esperar su frecuencia habitual. La lectura completa y
exitosa actualiza datos, hora y conexión en la misma transacción. Una prueba de
credenciales por sí sola no elimina el aviso de desconexión. El formulario espera
hasta 30 segundos y recarga la ficha al detectar una lectura nueva; si sigue
pendiente lo comunica. La frecuencia configurada se conserva. El programador debe
estar encendido; al arrancar hace una lectura de todas las conexiones elegibles
para recuperar avisos emitidos mientras estuvo detenido.

El historial acordado incluye estados operativos y de conexión, presencia y salud
de componentes, mantenimiento, baja y asignación de clúster. No se implementa una
auditoría general de firmware, sistema operativo o datos administrativos (E6).
La selección de alertas permanece según la decisión del autor; las fechas de
historial y alertas se presentan explícitamente en la zona America/Lima.


## Despliegue Linux con Docker y PostgreSQL en AWS

La configuración de los cinco servicios, el uso de la llave original, TLS hacia AWS y las verificaciones previas están en [despliegue/README.md](despliegue/README.md). Se mantienen 5173, 8080, 8001 y las direcciones de los 17 simuladores. No se crea una base local ni se modifica el esquema automáticamente.
