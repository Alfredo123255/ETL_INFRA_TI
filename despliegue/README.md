# Despliegue en Linux: PostgreSQL en AWS y SNMP simulado

El paquete contiene cinco servicios: frontend (5173), backend (8080), FastAPI (8001), ETL periódico y los 17 agentes SNMP. PostgreSQL permanece en AWS (5432). No incluye una base local ni crea o modifica el esquema.

## 1. Qué copiar al servidor

Descomprime `infra-ti-linux-docker.zip`, por ejemplo en `/opt/infra-ti`. Deben quedar estas carpetas al mismo nivel:

```text
/opt/infra-ti/
  backend/       # Java: fuentes de producción, pom y Dockerfile
  frontend/      # React: fuentes, archivos públicos, lock y Nginx
  etl/           # Python: API, ETL y datos mínimos de los simuladores
  despliegue/    # Compose y esta guía
```

No copies entornos virtuales, node_modules, target, pruebas, MIB, scripts auxiliares de Windows ni registros. Los Dockerfile construyen los ejecutables dentro de Docker. Los simuladores sí necesitan sus `public.snmprec`; ya están incluidos.

El frontend conserva el árbol del lock actual con `npm ci --legacy-peer-deps`: la biblioteca de mapas declara compatibilidad hasta React 18 y el proyecto usa React 19. Esta opción evita el rechazo de instalación sin cambiar las versiones del producto. [Comportamiento documentado de npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/). Conviene resolver esa compatibilidad de la biblioteca en una actualización independiente; la compilación por sí sola no sustituye revisar el mapa en el navegador.

Instala Docker Engine con Compose en el servidor Linux siguiendo la [guía oficial](https://docs.docker.com/engine/install/). Esta configuración utiliza la red del host Linux para mantener exactamente las direcciones `127.0.0.x` de los simuladores y sus puertos. [Documentación de red host](https://docs.docker.com/engine/network/drivers/host/).

## 2. Preparar AWS y la configuración privada

La base de AWS debe tener el esquema y los datos que quieres conservar. Este paquete no traslada automáticamente la base local. Si AWS aún está vacío, restaura un respaldo completo de la base existente antes de arrancar; revisa el destino antes de restaurar. No ejecutes `schema.sql` sobre una base existente para intentar actualizarla.

Completa `despliegue/.env` a partir de `.env.example`:

- `DB_HOST`: endpoint directo de PostgreSQL en AWS, sin protocolo ni puerto.
- `DB_NAME`, `DB_USERNAME` y `DB_PASSWORD`: base existente y credenciales de AWS. El nombre de la base debe usar letras, números o guion bajo para esta URL JDBC.
- `ETL_API_KEY`: la misma clave privada para backend y FastAPI; la copia privada preparada ya conserva la actual.
- `PUBLIC_ORIGIN`: dirección desde la que entrarás al frontend, por ejemplo `http://192.0.2.10:5173`.

Las rutas de contexto del ejemplo corresponden al ZIP. Si ejecutas Compose desde los repositorios separados, ajusta las tres rutas a sus carpetas reales; `ETL_CONTEXT=..` cuando Compose está en `ETL_INFRA_TI/despliegue`.

Desde Linux se necesita acceso TCP al endpoint AWS:5432. En AWS configura el acceso desde la IP o red del servidor Linux. El ETL usa una conexión de sesión directa para las notificaciones y el bloqueo del programador; evita un intermediario que cambie de sesión por transacción.

El paquete ya incluye el certificado público de Amazon RDS en `certs/postgres-ca.pem`. Para renovarlo desde la fuente oficial:

```sh
cd /opt/infra-ti/despliegue
mkdir -p certs secrets
curl --fail --show-error --location \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  --output certs/postgres-ca.pem
chmod 644 certs/postgres-ca.pem
```

Se utiliza TLS con verificación del servidor (`verify-full`) tanto en Java como en Python. Usa el endpoint que corresponde al certificado, no una IP inventada. [TLS en RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html), [certificados de RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html). Si PostgreSQL está instalado por ti en EC2, sustituye el certificado por la CA que firma ese servidor y comprueba que PostgreSQL tenga TLS configurado; el certificado RDS no sirve para una instalación propia.

## 3. Conservar la llave original

Copia de forma privada la llave actual a `despliegue/secrets/snmp_credentials.key`. Debe ser exactamente la misma con la que se cifraron las filas de la base, incluso si restauras el respaldo en AWS. No generes otra para este despliegue.

En el equipo de desarrollo está en `C:\Users\jenny\.config\infra-ti\snmp_credentials.key`. También está documentada en la guía privada de esa misma carpeta. La carpeta privada de despliegue contiene una copia preparada; no está en Git ni en el ZIP público.

Da acceso de lectura al grupo 10001 que utilizan Java y Python:

```sh
sudo chown root:10001 secrets secrets/snmp_credentials.key
sudo chmod 750 secrets
sudo chmod 440 secrets/snmp_credentials.key
chmod 600 .env
```

Compose monta la llave como archivo de solo lectura en `/run/secrets/snmp_credentials.key`; no queda dentro de las imágenes. [Secretos en Compose](https://docs.docker.com/compose/how-tos/use-secrets/). Conserva un respaldo privado de la llave y de la base.

## 4. Construir, verificar y arrancar

Antes de iniciar, comprueba que 5173/TCP, 8080/TCP, 8001/TCP y los puertos UDP de los agentes (16100 a 17700, de 100 en 100) estén libres. No debe haber otro grupo de simuladores ni otro ETL consultando la misma base. Al trasladarte desde Windows, detén su ETL antes de activar el nuevo; no inicies dos instalaciones sobre la misma base durante la transición.

```sh
cd /opt/infra-ti/despliegue
docker compose config --quiet
docker compose build
docker compose run --rm --no-deps fastapi python docker/preflight.py
```

La tercera orden consulta la base en modo de solo lectura: comprueba TLS, dos columnas necesarias del esquema, recuentos y que la llave pueda descifrar las credenciales existentes. No ejecuta el ETL. El backend valida adicionalmente el mapeo completo de entidades al arrancar (`ddl-auto=validate`). Si falla, corrige el acceso, el certificado, la llave o revisa la compatibilidad del esquema existente antes de seguir.

Si las verificaciones son correctas:

```sh
docker compose up -d --wait --wait-timeout 240
docker compose ps
docker compose logs --tail 80 etl
```

Abre `http://IP_DEL_SERVIDOR:5173`. El frontend dirige `/api` al backend; FastAPI y backend escuchan en loopback. El ETL empieza con su lectura normal de arranque y continúa según los intervalos de las conexiones almacenadas en AWS. No necesita cron ni una tarea programada externa. `restart: unless-stopped` lo vuelve a iniciar con Docker.

La comprobación de salud de los simuladores hace únicamente lecturas SNMP. Espera hasta que los 17 respondan antes de arrancar la API. No cambia los estados de los activos en la base. Los dispositivos en Baja/Inactivo conservan la exclusión que ya aplica el ETL.

## 5. Operación y límites de esta entrega

```sh
docker compose logs --tail 100 fastapi backend etl
docker compose stop
# Para reanudar después de detenerlos:
docker compose up -d --wait --wait-timeout 240
```

Los simuladores usan los datos incluidos en la imagen. Si cambias un `.snmprec` en las fuentes del servidor, reconstruye y recrea el servicio `simuladores`; no edites archivos dentro del contenedor. Sus credenciales siguen siendo HPE / Enterprise y Huawei: Administrator / Admin@9000 (autenticación y privacidad SHA/AES, contexto public).

En este equipo de desarrollo no hay motor Docker. Se verifican la configuración de Compose, las dependencias y la compilación del código; la construcción y ejecución real de las imágenes debe comprobarse en Linux con las órdenes anteriores. El acceso a AWS y el certificado del destino solo pueden verificarse después de completar los datos reales. Esta entrega no certifica todavía un despliegue activo en AWS.

La configuración publica el frontend por HTTP en 5173 para conservar el puerto actual. Si se expondrá a Internet, prepara el dominio y HTTPS en el servidor antes de introducir credenciales desde redes externas; ajusta `PUBLIC_ORIGIN` al origen final.
