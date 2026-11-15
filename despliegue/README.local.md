# Docker en la otra PC, con PostgreSQL en AWS

Este archivo prepara el despliegue en la PC de destino con los puertos habituales: frontend 5173, Java 8080 y FastAPI 8001. PostgreSQL sigue en AWS. No se crea una base paralela, no se restaura ningún respaldo y el Compose no ejecuta migraciones.

Se incluyen cinco servicios: frontend, backend, FastAPI, programador ETL y los 28 simuladores del manifiesto. Se reutilizan los Dockerfile actuales y la configuración de autenticación existente. Para esta preparación no se arrancó ningún servicio en la PC de desarrollo.

## Archivos y configuración en la PC de destino

Instala o inicia Docker con contenedores Linux. En Windows puede utilizarse Docker Desktop con WSL 2; en Linux, Docker Engine con Compose. No hace falta Python, Java, Maven ni Node instalados directamente en esa PC.

La estructura por defecto es la actual:

```text
carpeta-de-trabajo/
  ETL_INFRA_TI/
    data/
    despliegue/
      compose.local.yaml
      .env.local.example
      certs/postgres-ca.pem
      secrets/snmp_credentials.key   # archivo privado, se copia por separado
  Backend-SI-INFRA-TI/
    backend-infra-ti/
  Frontend-SI-INFRA-TI/
    Frontend-SI-INFRA-TI/
```

Desde `ETL_INFRA_TI/despliegue`, copia `.env.local.example` a `.env.local` y completa:

- El endpoint, puerto, nombre de base y usuario de PostgreSQL en AWS. El nombre de base debe usar letras, números o guion bajo, como en el Compose de Linux existente.
- La contraseña de AWS, únicamente en `.env.local`.
- Una misma `ETL_API_KEY` para Java y FastAPI. Compose entrega el mismo valor a ambos.
- `PUBLIC_ORIGIN`: la dirección exacta que usarás para abrir la aplicación, por ejemplo `http://localhost:5173` si la abres en la PC de destino, o `http://IP_DE_LA_OTRA_PC:5173` si accedes desde otra PC. Usa una dirección real, sin barra final.

Las rutas de los tres repositorios pueden ajustarse en ese archivo si las carpetas se copiaron con otros nombres. Usa `/` en rutas absolutas de Windows. `.env.local` está excluido de Git; el ejemplo no contiene contraseñas ni llaves.

Coloca el certificado de la CA de PostgreSQL en `certs/postgres-ca.pem` y la llave SNMP original en `secrets/snmp_credentials.key`. La llave debe corresponder a las credenciales cifradas de esa base; no se genera ni se cambia con este Compose. En Linux, los procesos de las imágenes usan UID/GID 10001 y necesitan acceso de lectura a esos archivos. La guía principal `README.md` explica los permisos y el certificado de AWS.

AWS debe admitir la conexión desde la PC de destino y la base debe tener el esquema y los datos actuales. El backend valida el esquema al arrancar; no lo modifica. Antes de trasladar el monitoreo, detén el programador anterior que apunte a esa misma base. El bloqueo de PostgreSQL evita que dos programadores funcionen simultáneamente, pero conviene hacer una transición ordenada.

## Primer administrador

Si la tabla de usuarios está vacía y el esquema y los roles iniciales ya están instalados, completa `ADMIN_CORREO`, `ADMIN_NOMBRE` y `ADMIN_CONTRASENA` únicamente en el archivo privado `.env.local`. El backend crea al primer administrador al arrancar y guarda la contraseña como hash BCrypt en la base.

Las tres variables son opcionales: si falta alguna, no se crea la cuenta. Si ya existe cualquier usuario, la creación inicial no se ejecuta y esas variables no cambian contraseñas. Para una base con tus usuarios actuales, inicia sesión con la cuenta que ya existe allí.

Tras crear la cuenta puedes vaciar esas tres variables del archivo privado. No se eliminan automáticamente del archivo. Mantenerlas no restablece la contraseña en los reinicios, pero ya no hacen falta para iniciar sesión. Nunca copies sus valores al ejemplo, al Compose, a una imagen o a Git.

## Construir y verificar

Ejecuta en la otra PC, desde `ETL_INFRA_TI/despliegue`:

```powershell
docker compose --env-file .env.local -f compose.local.yaml config --quiet
docker compose --env-file .env.local -f compose.local.yaml build
docker compose --env-file .env.local -f compose.local.yaml run --rm --no-deps fastapi python docker/preflight.py
```

La última orden verifica PostgreSQL, TLS, esquema y descifrado con una transacción de solo lectura; no arranca el ETL. Se requieren los archivos privados y el acceso de red a AWS. No compartas la salida completa de `docker compose config` sin `--quiet`, porque puede incluir variables privadas.

## Arrancar

```powershell
docker compose --env-file .env.local -f compose.local.yaml up -d --wait --wait-timeout 300
docker compose --env-file .env.local -f compose.local.yaml ps
docker compose --env-file .env.local -f compose.local.yaml logs --tail 60 etl
```

Abre la URL que pusiste en `PUBLIC_ORIGIN`. Java y FastAPI quedan accesibles para Postman **desde la PC de destino** en `http://localhost:8080` y `http://localhost:8001`; sus puertos se publican solo en el loopback del host. El frontend se publica en 5173 para poder acceder desde la red cuando el firewall de la PC lo permita. No publiques este HTTP directamente en Internet; el despliegue público requiere su dominio y HTTPS.

No necesitas encender los agentes con `start_agents.bat`: el servicio `simuladores` los administra dentro de Docker. El programador ETL también arranca desde Compose y utiliza las frecuencias de la base existente.

## Cómo se conservan las IP SNMP

Los cinco servicios comparten el espacio de red del contenedor `simuladores` mediante `network_mode: service:simuladores`. Así las direcciones `127.0.0.x` almacenadas en las conexiones apuntan a los agentes de Docker, sin cambiar esas filas de la base. No se usa `network_mode: host`, por lo que no depende de activar la red host de Docker Desktop. Solo el servicio dueño de ese espacio publica los tres puertos.

El directorio `data` de la PC de destino se monta para lectura en `/app/data`. Debe contener el manifiesto, los scripts de agentes, `variation/` y las carpetas con sus `public.snmprec`. Editar las capturas desde el host modifica lo que lee el agente; no es necesario reconstruir la imagen para cambiar un `.snmprec`. Los scripts de retiro/restauración pueden utilizarse en Windows sobre ese directorio con el agente encendido; para ejecutar esos auxiliares desde el host sí hace falta su entorno Python. La aplicación dentro de Docker no lo necesita.

Si cambias o recreas el servicio `simuladores`, ejecuta el `up` del proyecto completo para que Compose actualice también los servicios que comparten su red. Los cambios de captura no requieren recrearlo.

## Detener y reanudar

```powershell
docker compose --env-file .env.local -f compose.local.yaml stop
docker compose --env-file .env.local -f compose.local.yaml up -d --wait --wait-timeout 300
```

Detener los contenedores no elimina ni revierte datos en AWS. Una vez encendido el ETL, este sí realiza las actualizaciones normales de activos, componentes, métricas e historial sobre la base configurada.

Referencias: [red compartida entre servicios](https://docs.docker.com/reference/compose-file/services/#network_mode), [dependencias por estado de salud](https://docs.docker.com/reference/compose-file/services/#depends_on), [Docker Desktop en Windows](https://docs.docker.com/desktop/setup/install/windows-install/).
