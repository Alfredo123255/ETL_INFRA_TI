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

Además de los 7 módulos propietarios, `ip_sistema_operativo` (sección 3) usa el módulo **estándar**
`IP-MIB` (RFC 4293/RFC 1213, no HPE-específico, no vive en `mibs/hpe-real/` porque no es propietario
de Compaq/HPE), resuelto igual que las dependencias RFC de arriba: vía el mismo espejo
`https://mibs.pysnmp.com/asn1/@mib@` con `pysnmp`, no derivado a mano.

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
| `ip_sistema_operativo` | `1.3.6.1.2.1.4.20.1.1` (`ipAdEntAddr`), tabla `ipAddrTable` | **IP-MIB (estándar, RFC 1213/4293)**. El único campo de IP en `CPQHOST-MIB` es `cpqHoClientIpAddress`, que es la IP de una *consola de gestión remota* registrada, no la IP propia del servidor — por eso se usa el `IP-MIB` estándar en su lugar. `ipAdEntIfIndex` (`...4.20.1.2`) referencia el índice de interfaz que porta esa IP; en los servidores rack (`hpe-dl380-01`/`hpe-dl360-01`) se usa el índice de `cpqNicIfPhysAdapterTable` (sección 4.6) ya que este agente no expone `IF-MIB` propio, y en los blades (`hpe-bl460c-01`/`hpe-bl460c-02`, sin tabla de NIC propia — ver sección "Servidores tipo BLADE") se deja `1` como referencia genérica. |
| `version_so` | `1.3.6.1.4.1.232.11.2.2.2` (`cpqHoVersion`) | CPQHOST-MIB | DisplayString, "The version of the host OS." Complementario: `cpqHoName` (`...11.2.2.1`) da el nombre del SO y `cpqHosysDescr` (`...11.2.2.13`) da el equivalente a `sysDescr`. |
| `version_firmware` | `1.3.6.1.4.1.232.1.2.6.1` (`cpqSeSysRomVer`) | CPQSTDEQ-MIB | DisplayString, "System ROM version information." Es la versión de ROM/BIOS del sistema en general (grupo `cpqSeRom`), no de un componente específico. Se revisaron los 7 módulos ya usados más `cpqsm2` y `cpqrecov` buscando un OID de firmware a nivel de servidor completo; el resto de campos de firmware encontrados son por componente (ej. `cpqHeFltTolPowerSupplyFirmwareRev`, `cpqDaCntlrOptionRomRev`), no equivalentes a este. La fecha de publicación del firmware viene incluida como texto dentro de este mismo valor (ej. `"U30 v2.78 (03/22/2023)"`) — no existe un OID de fecha aparte, así que no hace falta (ni es posible) separarlas; ver sección 5 para el detalle de por qué. |

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
| `serie` | `1.3.6.1.4.1.232.2.2.4.5.1.10` (`cpqSiMemModuleSerialNo`) | DisplayString. Columna de la misma tabla `cpqSiMemModuleTable`, no se había poblado en la primera pasada de este mapeo — ya estaba identificada como real, sólo faltaba la fila de datos. |
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

### 4.6 Tarjetas de red y sus puertos (`CPQNIC-MIB`, tabla `cpqNicIfPhysAdapterTable`, índice `cpqNicIfPhysAdapterIndex`)

Esta tabla modela **un puerto físico por fila** (no una tarjeta con N puertos), confirmado
leyendo directamente `cpqnic.mib`: no existe ninguna tabla separada de "tarjetas" en este
módulo. Para llenar dos conceptos distintos en el sistema de monitoreo — **tarjeta de red**
(modelo, cantidad de puertos, estado agregado) y **puerto de red** (número de puerto, MAC,
velocidad, estado) — el ETL debe:

1. **Agrupar filas por tarjeta usando `cpqNicIfPhysAdapterSlot`** (columna `...1.1.5`, ver abajo):
   todas las filas con el mismo valor de `Slot` pertenecen a la misma tarjeta física. Esta es la
   única columna de la tabla pensada explícitamente para identificar el hardware físico que
   implementa cada interfaz (su descripción real: *"The number of the slot containing the
   physical hardware that implements this interface. The number zero (0) indicates an embedded
   interface"*). `cpqNicIfPhysAdapterPciLocation` (`...1.1.43`, texto libre de ubicación PCI)
   podría servir como agrupador alternativo más granular, pero `Slot` es el campo numérico
   normalizado que ya usa este MIB para ese propósito.
2. Dentro de cada grupo (`tarjeta`), cada fila es un `puerto`, distinguido por
   `cpqNicIfPhysAdapterPort` (columna `...1.1.10`, número de puerto dentro de la tarjeta
   multi-puerto).

En los agentes simulados: `hpe-dl380-01` tiene dos tarjetas distintas (`Slot=0` para el LOM
331i embebido, `Slot=1` para el 562FLR-SFP+ add-in), una fila = un puerto cada una;
`hpe-dl360-01` tiene una sola tarjeta (`Slot=0`, el 331i embebido de 4 puertos), con dos filas
(`Port=1` y `Port=2`) representando dos de sus puertos.

| Campo | OID (columna) | Notas |
|---|---|---|
| `marca` (tarjeta) | **No disponible como campo separado.** `cpqNicIfPhysAdapterName` (DisplayString libre, `1.3.6.1.4.1.232.18.2.3.1.1.39`) suele incluir el fabricante en el texto (ej. "HPE Ethernet 1Gb 4-port 331i"), pero no hay un campo de marca aislado. |
| `modelo` (tarjeta) | `1.3.6.1.4.1.232.18.2.3.1.1.39` (`cpqNicIfPhysAdapterName`) — alternativa: `cpqNicIfPhysAdapterPartNumber` (`...1.1.32`) | Se usa `Name` como texto de modelo comercial; `PartNumber` es el part number HPE. Si la tarjeta tiene más de un puerto simulado, todas sus filas comparten el mismo `Name`/`PartNumber` (es el mismo hardware). |
| `cantidad_puertos` (tarjeta) | **Derivado, no es un único OID.** Se cuenta la cantidad de filas de `cpqNicIfPhysAdapterTable` que comparten el mismo `cpqNicIfPhysAdapterSlot` (ver agrupación arriba). `cpqNicIfLogMapAdapterCount` (`1.3.6.1.4.1.232.18.2.2.1.1.5`) NO sirve para esto: cuenta adaptadores agrupados en un *team* lógico (bonding/teaming), un concepto distinto al de puertos físicos de una misma tarjeta. |
| `numero_puerto` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.10` (`cpqNicIfPhysAdapterPort`) | INTEGER, "The port number of the interface for multi-port NICs." `-1` si no se pudo determinar. |
| `mac_address` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.4` (`cpqNicIfPhysAdapterMACAddress`) | OCTET STRING de 6 bytes (tipo `4x` en `.snmprec`, valor hex). Puede venir vacío en algunas configuraciones según el propio MIB. |
| `velocidad` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.36` (`cpqNicIfPhysAdapterSpeedMbps`) — alternativa/complemento: `cpqNicIfPhysAdapterSpeed` (`...1.1.33`, bits/seg) | Ambas `Gauge32`. El propio MIB indica que `Speed` (bps) se pone en `0` si la velocidad supera 4.294.967.296 bps (4 Gbps) y que en ese caso hay que usar `SpeedMbps` en su lugar — así se hizo para el puerto 562FLR de 10 Gb del DL380 (`Speed=0`, `SpeedMbps=10000`). |
| `estado` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.14` (`cpqNicIfPhysAdapterStatus`) | Enum propio `unknown(1)/ok(2)/generalFailure(3)/linkFailure(4)` → EstadoEnum. El MIB documenta que `cpqNicIfPhysAdapterCondition` (columna `...1.1.12`, ya usada en el mapeo original) **se deriva** de este campo (`ok`→`ok`, `linkFailure`→`failed`); se mantienen ambas columnas por compatibilidad con el mapeo previo, pero `Status` es la fuente más granular. |
| `estado` (tarjeta, agregado) | Derivado del peor `estado` entre los puertos del mismo `Slot` (ver `EstadoEnum`) | No hay un campo de condición a nivel de tarjeta completa en este MIB, sólo por puerto/fila; el estado de la tarjeta es un agregado de la ETL sobre sus puertos. |
| `trafico_entrada_bytes` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.37` (`cpqNicIfPhysAdapterInOctets`) | `Counter` (Counter32, `.snmprec` tag `65`). *"A count of Octets Received on the physical adapter."* `STATUS optional` en el MIB (no todos los adaptadores lo implementan), pero es un objeto real. |
| `trafico_salida_bytes` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.38` (`cpqNicIfPhysAdapterOutOctets`) | `Counter` (Counter32, tag `65`). Igual que `InOctets` pero de salida. |
| `errores_alineamiento` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.20` (`cpqNicIfPhysAdapterAlignmentErrors`) | `Counter` (Counter32, tag `65`). Tramas recibidas que no calzan en un número entero de octetos. |
| `errores_fcs` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.21` (`cpqNicIfPhysAdapterFCSErrors`) | `Counter` (Counter32, tag `65`). Tramas que fallan el chequeo de checksum (Frame Check Sequence). |
| `errores_recepcion` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.19` (`cpqNicIfPhysAdapterBadReceives`) | `Counter` (Counter32, tag `65`). Según la descripción del propio MIB es la **suma** de `AlignmentErrors` + `FCSErrors` + `FrameTooLongs` + `InternalMacReceiveErrors`; se usa como contador agregado de errores de entrada. |
| `errores_transmision` (puerto) | `1.3.6.1.4.1.232.18.2.3.1.1.18` (`cpqNicIfPhysAdapterBadTransmits`) | `Counter` (Counter32, tag `65`). Suma documentada de `DeferredTransmissions` + `LateCollisions` + `ExcessiveCollisions` + `CarrierSenseErrors` + `InternalMacTransmitErrors`; agregado de errores de salida. |

**Nota sobre tipos de contador (Counter32 vs Counter64):** `cpqnic.mib` sólo define estos
contadores como `Counter` (`SYNTAX Counter`), que en SMIv1 sólo existe en 32 bits — no hay
ningún contador de 64 bits (`Counter64`) en este módulo, a diferencia de `IF-MIB`/`ifXTable`
(que sí lo tiene, ver `MAPEO-CHASIS.md`). Por eso en `.snmprec` estos ocho contadores usan
siempre la etiqueta `65` (Counter32) — nunca `70` (Counter64) — con la forma de variación
`numeric` de snmpsim: `<OID>|65:numeric|rate=<por segundo>,initial=<valor>`.

**Contadores más finos disponibles en `cpqnic.mib` pero no poblados en esta simulación** (tienen
OID real, simplemente no se cargó una fila de datos para ellos, por alcance): `GoodReceives`
(`...1.1.17`), `GoodTransmits` (`...1.1.16`), `DeferredTransmissions` (`...1.1.24`),
`LateCollisions` (`...1.1.25`), `ExcessiveCollisions` (`...1.1.26`), `CarrierSenseErrors`
(`...1.1.28`), `FrameTooLongs` (`...1.1.29`), `InternalMacReceiveErrors` (`...1.1.30`),
`InternalMacTransmitErrors` (`...1.1.27`), `SingleCollisionFrames` (`...1.1.22`),
`MultipleCollisionFrames` (`...1.1.23`).

### 4.7 Controladoras RAID (`CPQIDA-MIB`, tabla `cpqDaCntlrTable`, índice `cpqDaCntlrIndex`; RAID level tomado de `cpqDaLogDrvTable`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `modelo` | `1.3.6.1.4.1.232.3.2.2.1.1.2` (`cpqDaCntlrModel`) | Enum de modelos Smart Array (`smart-p420`, `sa-p600`, etc. — lista extensa de valores nombrados, no texto libre) |
| `serie` | `1.3.6.1.4.1.232.3.2.2.1.1.15` (`cpqDaCntlrSerialNumber`) | DisplayString. Columna de la misma tabla `cpqDaCntlrTable`, no se había poblado en la primera pasada de este mapeo — ya estaba identificada como real, sólo faltaba la fila de datos. |
| `raid` | `1.3.6.1.4.1.232.3.2.3.1.1.3` (`cpqDaLogDrvFaultTol`) — tabla `cpqDaLogDrvTable`, relacionada a la controladora vía `cpqDaLogDrvCntlrIndex` | El nivel de RAID es una propiedad de la **unidad lógica**, no de la controladora en sí (una controladora puede tener varias unidades lógicas con RAID distinto); se toma la primera unidad lógica de cada controladora como representativa. Enum: `none/mirroring/dataGuard/raid50/raid60/raid10/...` (`mirroring(3)` = RAID1, `raid10(12)` = RAID10) |
| `estado` | `1.3.6.1.4.1.232.3.2.2.1.1.6` (`cpqDaCntlrCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum |

## 5. Resumen de campos NO disponibles vía estos MIB (no se inventan valores)

> **Corrección:** en una versión anterior de este documento, `cantidad_hilos` de CPU y
> `cantidad_puertos` de tarjeta de red aparecían en esta lista de "no disponibles". Es incorrecto:
> ambos **sí tienen origen real**, sólo que calculado a partir de más de un OID, no leído de un
> único OID — no es lo mismo que "sin fuente". `cantidad_hilos` = `cantidad_nucleos`
> (`cpqSeCpuCore`) × `cpqSeCPUCoreMaxThreads` (ver sección 4.1); `cantidad_puertos` = conteo de
> filas de `cpqNicIfPhysAdapterTable` que comparten el mismo `cpqNicIfPhysAdapterSlot` (ver
> sección 4.6). Los campos que sí quedan en esta lista son los que ningún OID real, ni solo ni
> combinado con otros, puede producir.

- `fabricante` (constante de aplicación, no OID)
- `generacion` de servidor (implícita en texto de `modelo`, sin campo propio)
- `cacheL1/L2/L3` no son "no disponibles" pero sí requieren tres lecturas indexadas de la misma
  columna (`cpqSeCpuCacheSize` filtrado por nivel), no tres OID distintos
- `marca` de discos (sólo texto de modelo, sin campo de fabricante aislado)
- `velocidad_rpm` de discos como número real (sólo hay un enum categórico de rangos)
- `generacion` de RAM (tecnología legacy, no DDR3/4/5)
- `modelo` de ventiladores (sin campo de modelo comercial en el MIB)
- `tipo_corriente` de fuentes de poder (AC/DC no está expuesto)
- `marca` de tarjetas de red (embebida en texto de `modelo`, sin campo aislado)
- fecha de actualización/publicación de `version_firmware` como campo aislado. Se revisaron los
  mismos 9 módulos (los 7 base + `cpqsm2` + `cpqrecov`) y ninguno expone una fecha de firmware
  propia: `cpqSiQuickTestRomDate` (CPQSINFO-MIB) es la fecha de un ROM de autodiagnóstico rápido
  distinto al BIOS/ROM principal; `cpqSiCurRevDate`/`cpqSiPrevRevDate` (CPQSINFO-MIB) son fechas
  de configuración de la utilidad EISA (concepto legacy, sin relación con firmware); y
  `cpqHoFwVerTable` (CPQHOST-MIB), aunque sí identifica la fila del ROM del sistema vía
  `cpqHoFwVerDeviceType=systemRom(23)`, no tiene columna de fecha en su `SEQUENCE` (solo
  `Version`, `Location`, `XmlString`, `KeyString`). La única fecha real disponible es la que
  viene como texto libre dentro del propio valor de `version_firmware`
  (`cpqSeSysRomVer`, ej. `"U30 v2.78 (03/22/2023)"`); si se necesita como campo aparte, habría
  que parsearla de ese string, no leerla de un OID distinto.

## 5.1 Servidores tipo BLADE: alcance distinto al de un servidor rack

Los agentes simulados `hpe-bl460c-01`/`hpe-bl460c-02` (ProLiant BL460c Gen10) son servidores de
tipo **BLADE**, montados en el chasis `hpe-c7000-01`. A diferencia de un servidor rack
(DL380/DL360), un blade **no tiene tarjetas de red, ventiladores ni fuentes de poder propias**:
comparte ese hardware con el resto del chasis. Por eso estos campos, aunque siguen existiendo
como conceptos en la ficha del servidor, **no se leen del agente del blade** sino del agente del
chasis (ver `MAPEO-CHASIS.md`):

| Campo (ficha de servidor) | De dónde sale para un BLADE |
|---|---|
| Tarjetas de red / puertos (sección 4.6 de este documento) | No aplica al agente del blade. El chasis expone `cpqRackNetConnectorTable` (módulos de interconexión) y, para los puertos concretos, el `IF-MIB` del chasis (`MAPEO-CHASIS.md`, puertos `X1`..`X8`/`d1`..`d4`). |
| Ventiladores | `cpqHeFltTolFanTable` no se puebla en el agente del blade; los ventiladores son del chasis (`cpqRackCommonEnclosureFanTable`, `MAPEO-CHASIS.md`). |
| Fuentes de poder | `cpqHeFltTolPowerSupplyTable` no se puebla en el agente del blade; las fuentes son del chasis (`cpqRackPowerSupplyTable`, `MAPEO-CHASIS.md`). |

Lo que **sí** reporta el propio agente del blade (mismos módulos y OID que un servidor rack,
sin diferencias de mapeo): datos generales (hostname, número de serie, modelo, estado
operativo), CPU (sección 4.1), RAM incluyendo `cpqSiMemModuleSerialNo` (sección 4.3), discos y
controladora RAID incluyendo `cpqDaCntlrSerialNumber` (secciones 4.2 y 4.7), temperatura
(sección 4.4 — sólo la tabla de sensores; nótese que `CPQHLTH-MIB` sí expone
`cpqHeTemperatureTable` a nivel de host individual también en un blade), consumo eléctrico
(`cpqHePowerMeterCurrReading`, sección 3) e IP del sistema operativo (`ip_sistema_operativo`,
IP-MIB, sección 3) — con la salvedad de que, al no exponer este agente su propio `IF-MIB`,
`ipAdEntIfIndex` no referencia ninguna fila local y se deja en `1` como valor nominal.

## 6. Campos generados por el ETL (ni SNMP ni manual)

- `ultima_actualizacion`: no se lee de SNMP ni se llena a mano. El ETL asigna la fecha
  actual de Lima **antes de la carga**, después de preparar los datos del activo.
  El esquema R6 almacena DATE, por lo que este campo no conserva la hora.
  No corresponde agregarlo a ningún `public.snmprec`.

### Ubicación y nombres de serie en el esquema R6

- `sysLocation.0` (`1.3.6.1.2.1.1.6.0`, objeto estándar) está poblado en los
  simuladores rack con textos como `DataCenter-1 / Rack A12 / U18-19`. El extractor
  conserva ese texto. `activo.ubicacion` referencia `datacenters(nombre)`, por lo
  que se necesita una regla explícita para resolver el nombre del datacenter.
- `serie` en los componentes equivale a `numero_serial` en el esquema. El activo
  mantiene su columna `numero_serie`. Las MIB también permiten consultar
  `cpqDaPhyDrvSerialNum` (columna 51 de la tabla de discos),
  `cpqHeFltTolPowerSupplySerialNumber` (columna 11 de fuentes) y
  `cpqSeCPUSerialNumber` (columna 16 de CPU); valores vacíos se conservan como NULL.
- `cpuTotalGhz` lo calcula el backend a partir de las CPUs. `cpuUsoGhz` y
  `ramUsoGb` son mediciones históricas, no columnas de la tabla `servidor`.
