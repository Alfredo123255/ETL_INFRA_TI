# Mapeo de campos del sistema de monitoreo → OID reales de HPE/Compaq

## 0. Nota sobre el origen de esta carpeta

`mibs/hpe-real/` se generó copiando, desde la carpeta plana `mibs/` del repositorio, todos los
archivos con prefijo `cpq*`, `compaq*` y `hp*` (146 archivos: 74 `.mib` + sus `.cfg`). Esa carpeta
plana contiene en total 628 MIB de múltiples fabricantes (Cisco/H3C, Adaptec, Ashcroft, switches
genéricos, etc.), **no** una carpeta `hpe-real/` preexistente ni un MIB Kit de 316 archivos como se
asumía inicialmente. El subconjunto HPE/Compaq real (146 archivos) sí incluye los cuatro módulos
que necesitamos para un ProLiant (`cpqhlth`, `cpqida`, `cpqstsys`, `cpqnic`) además de módulos de
switch/blade/SAN (`cpqSasSwitch`, `hp-switch-pl`, `hpswitchpl`, `hpsgcluster`, `cpqcmc`, `cpqrack`,
`Synergy*`, `hpvcmodule`, etc.) que se ignoraron para este trabajo por no aplicar a un servidor rack
standalone.

## 1. Módulos identificados y nombre real del módulo ASN.1

| Archivo | Módulo ASN.1 real (línea `DEFINITIONS ::= BEGIN`) | Rol |
|---|---|---|
| `cpqhlth.mib` | `CPQHLTH-MIB` | Salud/ambiental: temperatura, ventiladores, fuentes de poder, medidor de consumo, memoria resiliente, condición general |
| `cpqida.mib` | `CPQIDA-MIB` | Storage/RAID: controladoras, unidades lógicas (RAID), discos físicos |
| `cpqstsys.mib` | `CPQSTSYS-MIB` | **Nota:** pese al nombre, este módulo es "Storage System" — describe gabinetes/drive-boxes de almacenamiento externo (enclosures), no el servidor host. No aportó campos a este mapeo; se mantiene en la carpeta por si se simulan cabinas externas más adelante. |
| `cpqnic.mib` | `CPQNIC-MIB` | Red: adaptadores físicos y mapeo lógico de NIC |
| `cpqhost.mib` | `CPQHOST-MIB` | Sistema operativo host: nombre, versión, uso de CPU, memoria física, sysDescr |
| `cpqsinfo.mib` | `CPQSINFO-MIB` | Información de sistema/chasis: número de serie, nombre de producto, módulos de memoria (tabla legacy) |
| `cpqstdeq.mib` | `CPQSTDEQ-MIB` | Equipamiento estándar: tabla de CPUs y tabla de caché de CPU |

Dependencias de `IMPORTS` resueltas dentro de la misma carpeta: `CPQHOST-MIB`, `CPQSINFO-MIB`,
`CPQSTDEQ-MIB` (además de los RFC estándar `RFC1155-SMI`, `RFC1213-MIB`, `RFC-1212`, `RFC-1215`,
resueltos por el espejo `https://mibs.pysnmp.com/asn1/@mib@`). Las siete carpetas anteriores fueron
compiladas con `pysmi` sin errores; los OID de este documento se resolvieron con `pysnmp`
(`MibBuilder.importSymbols` → `.getName()`), no derivados a mano de los comentarios del `.mib`.

## 2. Convención `EstadoEnum` usada en este mapeo

Casi todos los campos de condición HPE usan el patrón `other(1) / ok(2) / degraded(3) / failed(4)`
(a veces sin `other`, o con enums de estado más específicos). Se tradujeron así:

| Valor origen HPE | `EstadoEnum` |
|---|---|
| `ok(2)` | **Encendido** |
| `other(1)`, `degraded(3)` (o equivalentes "warning") | **Degradado** |
| `failed(4)` (o equivalentes "not present / missing") | **Apagado** |

**Limitación importante:** un agente SNMP que responde implica que el sistema host está encendido;
por lo tanto `estado_operativo` = "Apagado" a nivel de servidor completo no es algo que un agente
SNMP vivo pueda reportar de sí mismo (se infiere por *falta* de respuesta, no por un OID). El mapeo
de `estado_operativo` de todas formas usa `cpqHeMibCondition` con la tabla de arriba porque es el
OID de condición general más cercano que expone el MIB; el valor `Apagado` en ese campo específico
sólo se usará en la simulación como demostración del enum, no como algo que ocurriría en la
realidad con el agente arriba.

## 3. Campos generales del servidor

| Campo pedido | OID | Módulo | Tipo/notas |
|---|---|---|---|
| `hostname` | `1.3.6.1.4.1.232.11.2.2.12` (`cpqHoSystemName`) | CPQHOST-MIB | DisplayString, "Full computer name of the host" |
| `numero_serie` | `1.3.6.1.4.1.232.2.2.2.1` (`cpqSiSysSerialNum`) | CPQSINFO-MIB | DisplayString |
| `fabricante` | **No disponible como OID.** Ninguno de los 7 módulos expone un campo de fabricante explícito (todo el árbol es `enterprises.232` = Compaq/HPE por diseño, se asume implícito). Se dejará como constante fija de aplicación (`"HPE"`), no como valor leído de un OID. |
| `modelo` | `1.3.6.1.4.1.232.2.2.4.2` (`cpqSiProductName`) | CPQSINFO-MIB | DisplayString, ej. "ProLiant DL380 Gen10" |
| `generacion` | **No disponible como OID discreto.** Va implícita como subcadena dentro de `cpqSiProductName` (p. ej. "Gen10"), pero no hay un campo separado sólo para la generación. |
| `estado_operativo` | `1.3.6.1.4.1.232.6.1.3` (`cpqHeMibCondition`) | CPQHLTH-MIB | INTEGER `other/ok/degraded/failed` → ver tabla EstadoEnum arriba |
| `temperatura` | `1.3.6.1.4.1.232.6.2.6.8.1.4` (`cpqHeTemperatureCelsius`), instancia por sensor vía `cpqHeTemperatureLocale` (`...8.1.3`) | CPQHLTH-MIB | INTEGER, grados Celsius. Se usará el sensor `ambient(11)` como temperatura representativa del sistema. |
| `consumo_electico_w` | `1.3.6.1.4.1.232.6.2.15.3` (`cpqHePowerMeterCurrReading`) | CPQHLTH-MIB | INTEGER, vatios. Escalar (no tabla) |
| `cpuTotalGhz` | Derivado de `cpqSeCpuSpeed` (`1.3.6.1.4.1.232.1.2.2.1.1.4`, MHz) sumado/promediado por todas las entradas de `cpqSeCpuTable` | CPQSTDEQ-MIB | El MIB da MHz por CPU individual, no un total de sistema; `cpuTotalGhz` es un cálculo de la ETL (suma de `cpqSeCpuSpeed` de cada CPU física, convertido a GHz), no un OID único. |
| `cpuUsoGhz` | Derivado de `cpqHoCpuUtilMin` (`1.3.6.1.4.1.232.11.2.3.1.1.2`, % de uso) aplicado sobre `cpuTotalGhz` | CPQHOST-MIB | `cpqHoCpuUtilMin` es un **porcentaje** de utilización, no GHz. `cpuUsoGhz` = `cpuTotalGhz * (cpqHoCpuUtilMin/100)`, cálculo de la ETL. |
| `ramTotalGb` | `1.3.6.1.4.1.232.11.2.13.1` (`cpqHoPhysicalMemorySize`, MB) | CPQHOST-MIB | INTEGER en MB → convertir a GB |
| `ramUsoGb` | Derivado: `cpqHoPhysicalMemorySize` − `cpqHoPhysicalMemoryFree` (`1.3.6.1.4.1.232.11.2.13.2`, MB) | CPQHOST-MIB | Resta de dos OID, en MB → convertir a GB |
| `capacidadDiscosGb` | Suma de `cpqDaLogDrvSize` (`1.3.6.1.4.1.232.3.2.3.1.1.9`, MB) por cada unidad lógica del `cpqDaLogDrvTable` | CPQIDA-MIB | Sumatoria de la ETL sobre todas las filas, no un escalar único |
| `ip_sistema_operativo` | **No disponible en estos 7 módulos.** El único campo de IP en `CPQHOST-MIB` es `cpqHoClientIpAddress`, que es la IP de una *consola de gestión remota* registrada, no la IP propia del servidor. La IP real del host la expone el `IP-MIB`/`IF-MIB` estándar (fuera del alcance HPE de esta tarea). |
| `version_so` | `1.3.6.1.4.1.232.11.2.2.2` (`cpqHoVersion`) | CPQHOST-MIB | DisplayString, "The version of the host OS." Complementario: `cpqHoName` (`...11.2.2.1`) da el nombre del SO y `cpqHosysDescr` (`...11.2.2.13`) da el equivalente a `sysDescr`. |

## 4. Componentes

### 4.1 CPUs (`CPQSTDEQ-MIB`, tabla `cpqSeCpuTable`, índice `cpqSeCpuUnitIndex`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `marca` | `1.3.6.1.4.1.232.1.2.2.1.1.8` (`cpqSeCpuDesigner`) | Enum `intel(2)/amd(3)/...` |
| `modelo` | `1.3.6.1.4.1.232.1.2.2.1.1.3` (`cpqSeCpuName`) | DisplayString libre |
| `velocidad_ghz` | `1.3.6.1.4.1.232.1.2.2.1.1.4` (`cpqSeCpuSpeed`) | INTEGER en **MHz** → convertir a GHz |
| `cantidad_nucleos` | `1.3.6.1.4.1.232.1.2.2.1.1.15` (`cpqSeCpuCore`) | INTEGER directo |
| `cantidad_hilos` | **No hay OID de hilos totales por CPU.** Existe `cpqSeCPUCoreMaxThreads` (`...1.1.25`), pero es "máx. hilos **por núcleo**", no el total del paquete. `cantidad_hilos` = `cantidad_nucleos * cpqSeCPUCoreMaxThreads` es un cálculo derivado, no un único OID. |
| `cacheL1Mb` / `cacheL2Mb` / `cacheL3Mb` | Tabla separada `cpqSeCpuCacheTable`: `cpqSeCpuCacheSize` (`1.3.6.1.4.1.232.1.2.2.3.1.3`, KB) filtrado por `cpqSeCpuCacheLevelIndex` (`...3.1.2`) = 1/2/3 | Tres instancias del mismo OID de columna, una por nivel de caché; KB → convertir a MB |
| `estado` | `1.3.6.1.4.1.232.1.2.2.1.1.6` (`cpqSeCpuStatus`) | Enum propio `unknown/ok/degraded/failed/disabled` → EstadoEnum |

### 4.2 Discos (`CPQIDA-MIB`, tabla `cpqDaPhyDrvTable`, índices `cpqDaCntlrIndex`+`cpqDaPhyDrvIndex`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `marca` | **No disponible como campo separado.** `cpqDaPhyDrvModel` es un único DisplayString de texto libre que a veces incluye el fabricante embebido, pero no hay un campo de marca aislado. |
| `modelo` | `1.3.6.1.4.1.232.3.2.5.1.1.3` (`cpqDaPhyDrvModel`) | DisplayString |
| `tipo` | `1.3.6.1.4.1.232.3.2.5.1.1.60` (`cpqDaPhyDrvType`) | Enum `other/parallelScsi/sata/sas/nvme` |
| `capacidad_GB` | `1.3.6.1.4.1.232.3.2.5.1.1.45` (`cpqDaPhyDrvSize`) | INTEGER en MB → convertir a GB |
| `velocidad_rpm` | `1.3.6.1.4.1.232.3.2.5.1.1.59` (`cpqDaPhyDrvRotationalSpeed`) | **Enum categórico**, no un número de RPM real: `other(1)/rpm7200(2)/rpm10K(3)/rpm15K(4)/rpmSsd(5)`. Para poblar un valor numérico realista hay que mapear el enum a un RPM representativo (7200/10000/15000/0 para SSD) — es una conversión de la ETL, no un valor crudo del OID. |
| `estado` | `1.3.6.1.4.1.232.3.2.5.1.1.37` (`cpqDaPhyDrvCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum |

### 4.3 Memoria RAM (`CPQSINFO-MIB`, tabla `cpqSiMemModuleTable`, índices `cpqSiMemBoardIndex`+`cpqSiMemModuleIndex`)

> Nota: esta tabla está marcada `deprecated` dentro del propio `cpqsinfo.mib` desde la versión
> 8.20 del agente ("Deprecated this table in 8.20 time frame please use the cpqHeResMem2ModuleTable
> tables"), pero es la única de los 7 módulos que expone marca/modelo/velocidad/capacidad por DIMM
> individual — la tabla de reemplazo (`cpqHeResMem2BoardTable` en CPQHLTH-MIB) sólo da totales por
> placa, no por módulo. Se usa a propósito para poder cubrir todos los campos pedidos.

| Campo | OID (columna) | Notas |
|---|---|---|
| `marca` | `1.3.6.1.4.1.232.2.2.4.5.1.7` (`cpqSiMemModuleManufacturer`) | DisplayString |
| `modelo` | `1.3.6.1.4.1.232.2.2.4.5.1.8` (`cpqSiMemModulePartNo`) | DisplayString (part number del fabricante, se usa como "modelo") |
| `generacion` | **No disponible.** `cpqSiMemModuleTechnology` (enum `fastPageMode/edoPageMode/synchronous/rdram/...`) es tecnología de memoria de los 90, no generación DDR3/DDR4/DDR5. No hay campo DDR-generación en este MIB legacy. |
| `valocidad_mhz` | `1.3.6.1.4.1.232.2.2.4.5.1.13` (`cpqSiMemModuleFrequency`) | INTEGER en MHz directo |
| `capacidad_gb` | `1.3.6.1.4.1.232.2.2.4.5.1.3` (`cpqSiMemModuleSize`) | INTEGER en **KB** → convertir a GB |
| `estado` | `1.3.6.1.4.1.232.2.2.4.5.1.11` (`cpqSiMemModuleECCStatus`) | Enum `other/ok/degraded/degradedModuleIndexUnknown` → EstadoEnum (no tiene `failed` explícito; se trata `degradedModuleIndexUnknown` como Degradado también) |

### 4.4 Ventiladores (`CPQHLTH-MIB`, tabla `cpqHeFltTolFanTable`, índices `cpqHeFltTolFanChassis`+`cpqHeFltTolFanIndex`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `modelo` | **No disponible.** La tabla sólo tiene `cpqHeFltTolFanLocale` (ubicación: `system/cpu/powerSupply/...`, `1.3.6.1.4.1.232.6.2.6.7.1.3`) y `cpqHeFltTolFanType` (tipo de sensor, no modelo comercial). No hay texto de modelo de ventilador en este MIB. |
| `velocidad_rpm` | `1.3.6.1.4.1.232.6.2.6.7.1.12` (`cpqHeFltTolFanCurrentSpeed`) | INTEGER, RPM real (a diferencia del disco, aquí sí es un número directo) |
| `estado` | `1.3.6.1.4.1.232.6.2.6.7.1.9` (`cpqHeFltTolFanCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum |

### 4.5 Fuentes de energía (`CPQHLTH-MIB`, tabla `cpqHeFltTolPowerSupplyTable`, índices `cpqHeFltTolPowerSupplyChassis`+`cpqHeFltTolPowerSupplyBay`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `modelo` | `1.3.6.1.4.1.232.6.2.9.3.1.10` (`cpqHeFltTolPowerSupplyModel`) | DisplayString |
| `consumo_w` | `1.3.6.1.4.1.232.6.2.9.3.1.7` (`cpqHeFltTolPowerSupplyCapacityUsed`) | INTEGER, vatios en uso actual (existe también `cpqHeFltTolPowerSupplyCapacityMaximum`, `...1.8`, para la capacidad máxima) |
| `tipo_corriente` | **No disponible.** No existe un campo AC/DC explícito en la tabla; sólo `cpqHeFltTolPowerSupplyMainVoltage` (voltaje de entrada en volts), del cual no se puede inferir con certeza AC vs DC sin asumir umbrales arbitrarios. |
| `estado` | `1.3.6.1.4.1.232.6.2.9.3.1.4` (`cpqHeFltTolPowerSupplyCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum |

### 4.6 Tarjetas de red (`CPQNIC-MIB`, tabla `cpqNicIfPhysAdapterTable`, índice `cpqNicIfPhysAdapterIndex`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `marca` | **No disponible como campo separado.** `cpqNicIfPhysAdapterName` (DisplayString libre, `1.3.6.1.4.1.232.18.2.3.1.1.39`) suele incluir el fabricante en el texto (ej. "HPE Ethernet 1Gb 4-port 331i"), pero no hay un campo de marca aislado. |
| `modelo` | `1.3.6.1.4.1.232.18.2.3.1.1.39` (`cpqNicIfPhysAdapterName`) — alternativa: `cpqNicIfPhysAdapterPartNumber` (`...1.1.32`) | Se usa `Name` como texto de modelo comercial; `PartNumber` es el part number HPE |
| `cantidad_puertos` | **No disponible como conteo directo por tarjeta física.** Esta tabla modela **un puerto por fila** (indexada por `cpqNicIfPhysAdapterIndex`), no una tarjeta con N puertos. `cpqNicIfLogMapAdapterCount` (`1.3.6.1.4.1.232.18.2.2.1.1.5`) cuenta adaptadores agrupados en un *team* lógico (bonding/teaming), que es un concepto distinto. Contar puertos por tarjeta física requeriría agrupar filas por `cpqNicIfPhysAdapterSlot`/`cpqNicIfPhysAdapterPciLocation`, un cálculo de la ETL, no un OID. |
| `estado` | `1.3.6.1.4.1.232.18.2.3.1.1.12` (`cpqNicIfPhysAdapterCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum |

### 4.7 Controladoras RAID (`CPQIDA-MIB`, tabla `cpqDaCntlrTable`, índice `cpqDaCntlrIndex`; RAID level tomado de `cpqDaLogDrvTable`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `modelo` | `1.3.6.1.4.1.232.3.2.2.1.1.2` (`cpqDaCntlrModel`) | Enum de modelos Smart Array (`smart-p420`, `sa-p600`, etc. — lista extensa de valores nombrados, no texto libre) |
| `raid` | `1.3.6.1.4.1.232.3.2.3.1.1.3` (`cpqDaLogDrvFaultTol`) — tabla `cpqDaLogDrvTable`, relacionada a la controladora vía `cpqDaLogDrvCntlrIndex` | El nivel de RAID es una propiedad de la **unidad lógica**, no de la controladora en sí (una controladora puede tener varias unidades lógicas con RAID distinto); se toma la primera unidad lógica de cada controladora como representativa. Enum: `none/mirroring/dataGuard/raid50/raid60/raid10/...` |
| `estado` | `1.3.6.1.4.1.232.3.2.2.1.1.6` (`cpqDaCntlrCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum |

## 5. Resumen de campos NO disponibles vía estos MIB (no se inventan valores)

- `fabricante` (constante de aplicación, no OID)
- `generacion` de servidor (implícita en texto de `modelo`, sin campo propio)
- `ip_sistema_operativo` (requeriría IP-MIB/IF-MIB estándar, fuera de los módulos HPE pedidos)
- `cantidad_hilos` de CPU como valor directo (se deriva; no hay OID de hilos totales por paquete)
- `cacheL1/L2/L3` no son "no disponibles" pero sí requieren tres lecturas indexadas de la misma
  columna (`cpqSeCpuCacheSize` filtrado por nivel), no tres OID distintos
- `marca` de discos (sólo texto de modelo, sin campo de fabricante aislado)
- `velocidad_rpm` de discos como número real (sólo hay un enum categórico de rangos)
- `generacion` de RAM (tecnología legacy, no DDR3/4/5)
- `modelo` de ventiladores (sin campo de modelo comercial en el MIB)
- `tipo_corriente` de fuentes de poder (AC/DC no está expuesto)
- `marca` de tarjetas de red (embebida en texto de `modelo`, sin campo aislado)
- `cantidad_puertos` por tarjeta de red como conteo directo (la tabla es por puerto, no por tarjeta)
