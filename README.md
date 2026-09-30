# Entorno SNMP simulado — ETL (Objetivo 2)

Entorno para desarrollar y probar el componente ETL de extracción del Objetivo 2 de la tesis, sin depender de acceso real a switches HPE o Huawei. Los agentes SNMP se simulan localmente a partir de las MIB reales de cada fabricante, así que las OID y los tipos de dato que recibe el ETL son los mismos que recibiría de un equipo real, y el código de extracción no cambia el día que sí haya acceso a los equipos.

## Estructura

```
data/
  hpe-sw01/public.snmprec      # datos simulados del switch HPE
  huawei-sw01/public.snmprec   # datos simulados del switch Huawei
mibs/
  hp/                          # MIB de HPE (tomadas de LibreNMS)
  huawei/                      # MIB de Huawei (tomadas de LibreNMS)
src/
  extract.py                   # script de extracción (pysnmp)
requirements.txt
```

## Librerías

| Librería | Uso |
|---|---|
| `snmpsim` | Simula los agentes SNMP (switch HPE y switch Huawei) a partir de los `.snmprec`. Corre como proceso independiente vía `snmpsim-command-responder`. |
| `pysmi` | Dependencia de `snmpsim`/`pysnmp`, se instala sola. Traduce el texto de las MIB (`HUAWEI-DEVICE-MIB`, `HP-ICF-OID`, etc.) a algo que Python puede leer; por eso `--mib-source` apunta a esta librería, no a `snmpsim` directamente. |
| `pysnmp` | Cliente SNMP. Arma las consultas GET/GETBULK contra los agentes (simulados o reales), autenticando por SNMPv3 con `UsmUserData`/`ContextData`. |
| `pycryptodome` | Dependencia de `pysnmp`, se instala sola. Hace el cifrado/autenticación SHA y AES que exige SNMPv3. |

Pendientes para las siguientes etapas del ETL (normalización y carga):

| Librería | Uso previsto |
|---|---|
| `pandas` / `numpy` | Transformar los pares OID/valor crudos hacia el modelo de datos unificado. |
| `psycopg2` o `SQLAlchemy` | Cargar los datos ya normalizados en PostgreSQL. |

## Cómo correrlo

1. Instalar dependencias:
   ```
   pip install -r requirements.txt
   ```

2. Levantar el agente simulado (ejemplo con el switch HPE; para Huawei es el mismo comando cambiando `--data-dir`, el puerto y las credenciales):
   ```
   snmpsim-command-responder --data-dir=./data/hpe-sw01 --agent-udpv4-endpoint=127.0.0.1:1161 --v3-user=hpeadmin --v3-auth-key=hpeAuth2026 --v3-priv-key=hpePriv2026 --v3-auth-proto=SHA --v3-priv-proto=AES
   ```

3. En otra terminal, correr la extracción:
   ```
   python src/extract.py
   ```

## Regenerar los datos simulados

Si se necesita otra MIB o hay que rehacer un `.snmprec`:
```
snmpsim-record-mibs --mib-module=HUAWEI-DEVICE-MIB --output-file=./data/huawei-sw01/public.snmprec --mib-source=./mibs/huawei --mib-source=https://mibs.pysnmp.com/asn1/@mib@
```

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

Por ahora estas carpetas solo tienen la estructura de archivos (cada `.py` tiene únicamente un
docstring de módulo que describe su responsabilidad, las funciones/clases previstas y de qué
otros módulos depende; todavía no hay lógica implementada). El esquema de PostgreSQL pertenece a
otro módulo del sistema y es transversal: este repositorio no lo contiene ni lo crea, y el ETL
nunca hace DDL (crear/alterar/eliminar tablas), solo lee y escribe filas.

```
etl/
  __init__.py               # paquete del ETL
  config.py                 # carga la configuracion desde .env
  db.py                     # conexion a PostgreSQL (psycopg2, sin ORM); nunca toca el esquema
  repositorio.py            # consultas SQL parametrizadas (lectura de monitoreo_snmp, escritura de fichas/metricas)
  cifrado.py                # cifra/descifra las credenciales SNMPv3 guardadas en la base
  snmp_cliente.py           # GET/GETBULK/walk SNMPv3 con pysnmp
  detector.py                # resuelve que extractor/normalizador usar segun el tipo de activo
  metricas.py                # arma las filas de metrica historica a partir de la ficha normalizada
  carga.py                   # persiste ficha y metricas en la base via repositorio.py
  ciclo.py                   # orquesta extraer -> normalizar -> cargar para una conexion
  programador.py             # decide cuando correr cada extraccion (libreria schedule)
  extraccion/                # un modulo por tipo de activo: consulta los OID por SNMPv3
  normalizacion/             # un modulo por tipo de activo: pasa lo crudo a la estructura del esquema (pandas)
  oids/                      # constantes con los OID numericos transcritos de mibs/*.md, por tipo de activo
api/
  __init__.py                # paquete de la API
  main.py                     # FastAPI: probar conexion, extraer ahora, salud (no reemplaza al backend Spring Boot)
  dto.py                  # modelos pydantic de request/response
  seguridad.py                 # valida la cabecera X-API-Key
requirements.txt              # dependencias de Python del ETL y la API
.env.example                  # variables de entorno de ejemplo (nunca valores reales)
```

## API de validación de conexión

Esta sección describe la implementación actual y reemplaza, para estos módulos, la descripción
de estructura prevista de la sección anterior. Solo se implementa
`POST /api/etl/probar-conexion`: no hay base de datos, ORM, programador, guardado de credenciales
ni alta de activos. Los demás módulos del ETL siguen como estaban.

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

Instalar el simulador aparte si aún no está disponible:

```powershell
python -m pip install snmpsim
.\data\start_agents.bat
```

El archivo de arranque actual inicia siete agentes; **no incluye el chasis hpe-c7000-01**.
Para el octavo agente ejecutar el comando de
[data/hpe-c7000-01/README.md](data/hpe-c7000-01/README.md), con rutas absolutas.
Esta implementación no modifica `data/` ni `mibs/`.

Las IP actuales son distintas de `127.0.0.1`: el DL380 escucha en
`127.0.0.11:16100`. Utilizar el destino documentado para cada agente.

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
5. Sin evidencia o fallo de detección: DESCONOCIDO, manteniendo `ok=true` si el GET inicial funcionó.

El orden evita clasificar el storage como servidor por sus OID compartidos.
No se distingue blade de rack. Las bases se contrastaron con los MAPEO de chasis,
storage y servidor, y con los `public.snmprec`.

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

## Extracción y preparación del registro inicial de servidores HPE

Esta sección actualiza el estado de los módulos de servidor y reemplaza las
descripciones anteriores de módulos pendientes: ya están implementados la
extracción, normalización y registro inicial en PostgreSQL mediante
`POST /api/etl/crear-activo`. La ruta de prueba de conexión conserva su contrato.

- `etl/oids/servidor.py`: perfil HPE con escalares, columnas y enumeración de
  modelos de controladora transcrita de CPQIDA-MIB.
- `etl/snmp_cliente.py`: `ConexionSNMP` y `SesionSNMP`, con GET y recorridos
  GETBULK delimitados al subárbol; cierre del motor incluso al cancelar.
- `etl/extraccion/servidor.py`: `extraer_servidor_hpe(conexion)` devuelve valores
  ASN.1 por OID completo. La selección por fabricante no admite aún Huawei.
- `etl/normalizacion/servidor.py`: produce `activo`, `servidor`, `componentes`,
  `mediciones` y el texto original de `ubicacion_snmp`, con nombres del esquema.
- `etl/ciclo.py`: `preparar_registro_servidor` reutiliza la prueba de conexión,
  detección, extracción y normalización, sin guardar datos ni credenciales.
- `etl/db.py`, `etl/repositorio.py` y `etl/carga.py`: conexión, SQL parametrizado y
  transacción única para registrar activo, servidor, componentes, puertos y métricas.
- `etl/metricas.py`: prepara las mediciones para `metrica_historica`.

`cpuTotalGhz` queda a cargo del backend. `cpu_uso_ghz` y `ram_uso_gb` se devuelven
como mediciones, con los nombres que consume el backend y usa la migración de
Excel. La base para calcular el uso de CPU es la suma de velocidad en GHz ×
cantidad de núcleos de cada CPU; sobre esa capacidad se aplica el porcentaje
SNMP (promedio de las filas de utilización válidas). Si faltan velocidades o
núcleos válidos, no se genera una métrica de uso de CPU parcial.
`serie` de componentes se normaliza a `numero_serial`; la serie
del activo es `numero_serie`. La fecha `ultima_actualizacion` se asigna antes de
la futura carga, con fecha de Lima y tipo DATE. Los campos sin fuente quedan
vacíos; la revisión de arquitectura de CPU no se interpreta como familia.

La ubicación SNMP disponible usa textos como `DataCenter-1 / Rack A12 / U18-19`.
Se toma el texto antes del primer `/` como nombre del datacenter; debe existir en
`datacenters`. La solicitud puede enviar `ubicacion` para indicar explícitamente
un datacenter existente. Los servidores BLADE deben indicarse como tales; sus
componentes compartidos del chasis no se duplican ni se enlaza aún su slot.

### Registro inicial por API

Configurar `DATABASE_URL` y, opcionalmente, `DB_TIMEOUT` en `.env`. La prueba de
conexión no requiere estas variables. Instalar las dependencias actualizadas de
`requirements.txt`, incluido el controlador `psycopg2-binary`.

La base debe tener aplicado el esquema R6 por el módulo propietario del esquema
y estar poblado el catálogo de datacenters. El ETL no crea ni modifica tablas.

Enviar `X-API-Key` y este cuerpo a `POST /api/etl/crear-activo` (reemplazar los
marcadores de claves por los valores del agente, sin versionarlos):

```json
{
  "ip_gestion": "127.0.0.11:16100",
  "usuario": "monitor_dl380",
  "clave": "<clave de autenticación>",
  "clave_privacidad": "<clave de privacidad>",
  "tipo_servidor": "RACKEABLE"
}
```

`tipo_servidor` admite RACKEABLE (predeterminado) o BLADE. `ubicacion` es opcional.
El perfil implementado es HPE ProLiant; otros fabricantes o tipos se rechazan.

El proceso crea el modelo en `modelos` si no existe, inserta `activo` y `servidor`,
sus CPU, RAM, discos, controladoras RAID, tarjetas, puertos, ventiladores y fuentes
disponibles, y las métricas iniciales de uso de CPU/RAM, temperatura y consumo.
Si falla cualquier escritura, se deshace toda la transacción, incluido un modelo
nuevo. El registro inicial no actualiza activos existentes ni genera duplicados.

No se registra aún una fila en `monitoreo_snmp`, no se almacenan las credenciales
de la solicitud y no se configura frecuencia. Tampoco se genera un evento de
cambio en `historico_estado` por esta primera inserción.

Respuestas:

- 201: activo creado; devuelve `activo_id`, identidad, ubicación y cantidades guardadas.
- 401: clave de API ausente o incorrecta.
- 409: serie o hostname ya registrado.
- 422: solicitud, ficha o datacenter inválidos, o perfil no implementado.
- 502/504: fallo de comunicación SNMP o tiempo de espera agotado.
- 503: PostgreSQL no configurado, no disponible o fallo de persistencia.

Las mediciones se almacenan en UTC en el TIMESTAMP sin zona de `fecha_medicion`;
`activo.ultima_actualizacion` conserva únicamente la fecha de Lima.

Verificación de esta etapa:

```powershell
python -m pytest -q tests/unitarios tests/integracion/test_servidor.py
```

Las dos pruebas de integración de servidor levantan simuladores temporales en
puertos locales disponibles y los cierran al terminar. Requieren `snmpsim`.
Las pruebas de persistencia usan conexiones de prueba controladas para verificar
SQL parametrizado, relaciones, commit y rollback. La escritura contra PostgreSQL
real no se verificó en este entorno, que no tiene una conexión de base configurada.
