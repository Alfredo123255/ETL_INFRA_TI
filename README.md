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
