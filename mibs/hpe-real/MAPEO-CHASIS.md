# Mapeo de campos de ChasisBlade → OID reales de HPE/Compaq

## 0. Nota sobre el origen de esta carpeta

`cpqrack.mib` ya estaba presente en `mibs/hpe-real/` desde la copia inicial del subconjunto
HPE/Compaq (ver sección 0 de [`MAPEO-SERVIDOR.md`](./MAPEO-SERVIDOR.md)); no se agregó nada
nuevo a la carpeta para este trabajo, solo se investigó un archivo que ya estaba ahí y que en el
mapeo del servidor se había descartado por no aplicar a un ProLiant standalone.

## 1. Módulo identificado y nombre real del módulo ASN.1

| Archivo | Módulo ASN.1 real (línea `DEFINITIONS ::= BEGIN`) | Rol |
|---|---|---|
| `cpqrack.mib` | `CPQRACK-MIB` | Rack/enclosure: chasis blade, slots de servidor, fuentes de poder, ventiladores y conectores de red del enclosure (interconnects) |

Dependencia de `IMPORTS` resuelta dentro de la misma carpeta: `CPQHOST-MIB` (ya presente y
compilada del trabajo del servidor). `CPQRACK-MIB` se compiló con `pysmi` sin errores; los OID de
este documento se resolvieron con `pysnmp` (`MibBuilder.importSymbols` → `.getName()`), igual que
en `MAPEO-SERVIDOR.md`, no derivados a mano de los comentarios del `.mib`.

## 2. Convenciones de enum usadas en este mapeo

### 2.1 `EstadoEnum` (Activo, componentes) — igual que en `MAPEO-SERVIDOR.md`

| Valor origen HPE | `EstadoEnum` |
|---|---|
| `ok(2)` | **Encendido** |
| `other(1)`, `degraded(3)` (o equivalentes "warning") | **Degradado** |
| `failed(4)` (o equivalentes "not present / missing") | **Apagado** |

Misma limitación que en el servidor: un agente SNMP que responde implica que el chasis está
encendido, así que `estado_operativo` = "Apagado" no es algo que el propio agente pueda reportar
de sí mismo en la realidad; se usa igual como demostración del enum en la simulación.

### 2.2 `EstadoSlotEnum` (solo `chasisSlots`) — Ocupado / Libre / Degradado

`CPQRACK-MIB` no tiene un único campo con estos 3 valores exactos para un slot de blade; se
deriva combinando dos campos reales de `cpqRackServerBladeTable`:

| `cpqRackServerBladePresent` | `cpqRackServerBladeStatus` | `EstadoSlotEnum` |
|---|---|---|
| `absent(2)` | (no aplica) | **Libre** |
| `present(3)` | `ok(2)` | **Ocupado** |
| `present(3)` | `other(1)` / `degraded(3)` / `failed(4)` | **Degradado** |
| `other(1)` (no se pudo determinar presencia) | cualquiera | Se trata como **Libre** por defecto (no se puede confirmar ocupación); caso borde poco común |

Esto es una combinación de dos OID reales, no un campo forzado a un OID que no le corresponde.

## 3. Campos generales del chasis (`Activo` + específicos de `ChasisBlade`)

Tabla base: `cpqRackCommonEnclosureTable` (`CPQRACK-MIB`, índices `cpqRackCommonEnclosureRack`+
`cpqRackCommonEnclosureIndex`), salvo donde se indique otra tabla.

| Campo pedido | OID | Módulo | Tipo/notas |
|---|---|---|---|
| `hostname` | `1.3.6.1.4.1.232.22.2.3.1.1.1.9` (`cpqRackCommonEnclosureName`) | CPQRACK-MIB | DisplayString, "The name of the enclosure." Es el nombre administrativo del chasis, análogo al hostname que se usó para el servidor. |
| `numero_serie` | `1.3.6.1.4.1.232.22.2.3.1.1.1.7` (`cpqRackCommonEnclosureSerialNum`) | CPQRACK-MIB | DisplayString |
| `fabricante` | **No disponible como OID.** Igual que en el servidor, no hay un campo de fabricante explícito en el módulo; se deja como constante fija de aplicación (`"HPE"`). |
| `modelo` | `1.3.6.1.4.1.232.22.2.3.1.1.1.3` (`cpqRackCommonEnclosureModel`) | CPQRACK-MIB | DisplayString, ej. "BladeSystem c7000 Enclosure G2" |
| `generacion` | **No disponible como OID discreto.** Igual que en el servidor, va implícita como subcadena dentro de `cpqRackCommonEnclosureModel` (p. ej. "G2"), sin campo propio. |
| `estado_operativo` | `1.3.6.1.4.1.232.22.2.3.1.1.1.16` (`cpqRackCommonEnclosureCondition`) | CPQRACK-MIB | INTEGER `other/ok/degraded/failed` → EstadoEnum. Descripción textual: "aggregate of the temperature sensors, fans, and fuses within the enclosure." |
| `temperatura` | `1.3.6.1.4.1.232.22.2.3.1.2.1.6` (`cpqRackCommonEnclosureTempCurrent`), tabla `cpqRackCommonEnclosureTempTable` | CPQRACK-MIB | INTEGER, grados Celsius. A diferencia del servidor, aquí no hay un enum `Locale` (ambient/cpu/...) para elegir el sensor representativo — solo `cpqRackCommonEnclosureTempLocation` como texto libre; se usará el primer sensor de la tabla como representativo del chasis. |
| `consumo_electico_w` | `1.3.6.1.4.1.232.22.2.5.2.1.1.8` (`cpqRackPowerMeterWattage`), tabla `cpqRackPowerMeterTable` | CPQRACK-MIB | INTEGER, "The total wattage measured by the power meter" — es el medidor agregado de todo el chasis, análogo a `cpqHePowerMeterCurrReading` del servidor. Tabla y grupo distintos de `cpqRackPowerSupply*` (grupo `cpqRackPowerMeter`, no `cpqRackPowerSupply`), pero dentro del mismo módulo ya identificado. |
| `cantidad_slots` | `1.3.6.1.4.1.232.22.2.3.2.1.1.4` (`cpqRackServerEnclosureMaxNumBlades`), tabla `cpqRackServerEnclosureTable` (índices `cpqRackServerEnclosureRack`+`cpqRackServerEnclosureIndex`) | CPQRACK-MIB | INTEGER, "The maximum number of server blades the enclosure can contain." Tabla distinta de `cpqRackCommonEnclosureTable`, pero indexada con el mismo esquema Rack+Index del mismo enclosure. |

## 4. Componentes

### 4.1 `chasisSlots` (`CPQRACK-MIB`, tabla `cpqRackServerBladeTable`, índices `cpqRackServerBladeRack`+`cpqRackServerBladeChassis`+`cpqRackServerBladeIndex`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `numeroSlot` | `1.3.6.1.4.1.232.22.2.4.1.1.1.8` (`cpqRackServerBladePosition`) | INTEGER, "The position or slot number of the server blade within the server enclosure." (Existe también `cpqRackServerBladeIndex`, `...1.1.1.3`, que es el índice interno de la fila — normalmente coincide con el slot pero `Position` es el campo semánticamente correcto para "número de slot".) |
| `estado` | Derivado de `cpqRackServerBladePresent` (`...1.1.1.12`) + `cpqRackServerBladeStatus` (`...1.1.1.21`) | Ver tabla `EstadoSlotEnum` en la sección 2.2 — no es un único OID, es una combinación de dos. |
| `hostanameServidor` | `1.3.6.1.4.1.232.22.2.4.1.1.1.4` (`cpqRackServerBladeName`) | DisplayString, "The name of the server blade." La propia descripción del MIB indica "The string will be empty if it could not be determined" — coincide con el requisito de que quede vacío cuando el slot está Libre. |

### 4.2 Ventiladores (`CPQRACK-MIB`, tabla `cpqRackCommonEnclosureFanTable`, índices `cpqRackCommonEnclosureFanRack`+`cpqRackCommonEnclosureFanChassis`+`cpqRackCommonEnclosureFanIndex`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `modelo` | `1.3.6.1.4.1.232.22.2.3.1.3.1.6` (`cpqRackCommonEnclosureFanPartNumber`) | DisplayString — es un **part number** de HPE, no un nombre comercial de modelo (mismo tipo de campo que se usó como "modelo" en discos/RAM del servidor). No existe un campo de nombre/modelo comercial separado. |
| `velocidad_rpm` | **No disponible.** A diferencia de `cpqHeFltTolFanCurrentSpeed` del servidor, esta tabla no tiene ningún campo de velocidad ni de RPM — solo `Present`, `Redundant`, `RedundantGroupId` y `Condition`. |
| `estado` | `1.3.6.1.4.1.232.22.2.3.1.3.1.11` (`cpqRackCommonEnclosureFanCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum |

### 4.3 Fuentes de energía (`CPQRACK-MIB`, tabla `cpqRackPowerSupplyTable`, índices `cpqRackPowerSupplyRack`+`cpqRackPowerSupplyChassis`+`cpqRackPowerSupplyIndex`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `modelo` | `1.3.6.1.4.1.232.22.2.5.1.1.1.6` (`cpqRackPowerSupplyPartNumber`) | DisplayString, part number (mismo caso que el ventilador: no hay nombre comercial separado) |
| `consumo_w` | `1.3.6.1.4.1.232.22.2.5.1.1.1.10` (`cpqRackPowerSupplyCurPwrOutput`) | INTEGER, vatios de salida actual (existe también `cpqRackPowerSupplyMaxPwrOutput`, `...1.1.1.9`, para la capacidad máxima) |
| `tipo_corriente` | **No disponible por fuente individual.** La tabla de PSU no tiene campo AC/DC. Existe `cpqRackPowerEnclosureInputPwrType` (`1.3.6.1.4.1.232.22.2.3.3.1.1.7`, enum `other/singlePhase/threePhase/directCurrent`) en la tabla `cpqRackPowerEnclosureTable`, pero esa tabla describe el tipo de alimentación de **todo el dominio/enclosure de energía** (indexada por Rack+Index propios, sin relación directa a `cpqRackPowerSupplyIndex` de una fuente en particular), no de una fuente de poder individual — no se usa como equivalente para no forzar el mapeo. |
| `estado` | `1.3.6.1.4.1.232.22.2.5.1.1.1.17` (`cpqRackPowerSupplyCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum |

### 4.4 Tarjetas de red (`CPQRACK-MIB`, tabla `cpqRackNetConnectorTable`, índices `cpqRackNetConnectorRack`+`cpqRackNetConnectorChassis`+`cpqRackNetConnectorIndex`)

Esta tabla describe los módulos de interconexión de red del enclosure (interconnect bays), no
tarjetas de red de un servidor individual.

| Campo | OID (columna) | Notas |
|---|---|---|
| `marca` | **No disponible como campo separado.** Igual que en la tarjeta de red del servidor: puede venir embebida en el texto de `modelo`, sin campo de fabricante aislado. |
| `modelo` | `1.3.6.1.4.1.232.22.2.6.1.1.1.6` (`cpqRackNetConnectorModel`) | DisplayString, "The model name of the network connector." A diferencia del servidor (que no tenía un campo `Model` propiamente dicho, solo `Name`/`PartNumber`), aquí sí existe un campo de modelo comercial explícito. |
| `cantidad_puertos` | **No disponible.** La tabla no tiene ningún campo de conteo de puertos por conector/módulo. |
| `estado` | **No disponible.** A diferencia de las otras tres tablas de componentes de este mismo módulo (ventiladores, fuentes de poder, y del servidor: CPU/disco/RAM/NIC/RAID), `cpqRackNetConnectorTable` **no tiene ningún campo de condición/salud** en su `SEQUENCE` — solo `cpqRackNetConnectorPresent` (`other/absent/present`, presencia, no salud) y `cpqRackNetConnectorHasFuses` (remite a la tabla de fusibles, no es la condición del propio conector). No se fuerza `Present` como equivalente de `estado` porque presencia y condición de salud son conceptos distintos. |

### 4.5 Puertos del módulo de interconexión (`IF-MIB` estándar + `HPVCMODULE-MIB`)

`cpqRackNetConnectorTable` (sección 4.4) describe el **módulo** de interconexión completo, pero
`CPQRACK-MIB` no tiene ninguna tabla de **puertos** de ese módulo — se confirmó revisando todo
el `.mib`. Para modelar los puertos concretos del módulo de la bahía 1 (HPE Virtual Connect
Flex-10/10D, ver `cpqRackNetConnectorModel.1.1.1` en la sección 4.4) se usan dos módulos que no
son de la carpeta original de 7 módulos del servidor:

- **`IF-MIB` estándar** (RFC 2863, `1.3.6.1.2.1.2` / `1.3.6.1.2.1.31`), igual que
  `ip_sistema_operativo` en `MAPEO-SERVIDOR.md`. Se agregó `ifTable` **y** `ifXTable`
  (no sólo `ifTable`) porque `ifXTable` es la que aporta `ifName` (nombre corto de puerto,
  `X1`..`X8`/`d1`..`d4`) y los contadores de 64 bits (`ifHCInOctets`/`ifHCOutOctets`, ver nota
  de tipos más abajo).
- **`HPVCMODULE-MIB`** (`1.3.6.1.4.1.11.5.7.5.2.3`, propietario de HPE pero **sí** estaba ya en
  `mibs/hpe-real/` como `HPVCMODULE-MIB.mib` desde la copia inicial — ver sección 0 de
  `MAPEO-SERVIDOR.md`). Es el MIB que expone el módulo Virtual Connect en sí; su tabla
  `vcModulePortTable` (`...2.3.1.1.6`, índice `vcModulePort`) es la que documentada como *"a
  table that contains VC specific information about every port that is associated with this
  bridge"* — es decir, cubre tanto los puertos externos como los internos.

| Campo | OID | Módulo | Notas |
|---|---|---|---|
| Puerto (fila de interfaz) | `ifIndex` (`1.3.6.1.2.1.2.2.1.1`) | IF-MIB | Un `ifIndex` por puerto: `1`-`8` para `X1`-`X8` (externos, salida del módulo), `9`-`12` para `d1`-`d4` (internos, hacia los slots de blade) — la numeración X/d es una convención de nombres de este documento/simulación para demostrar el filtrado externo/interno, no algo que imponga el MIB. |
| `ifDescr`/`ifName` | `1.3.6.1.2.1.2.2.1.2` / `1.3.6.1.2.1.31.1.1.1.1` | IF-MIB | `ifName` trae el nombre corto (`X1`..`X8`, `d1`..`d4`); `ifDescr` trae una descripción más larga. |
| `ifType` | `1.3.6.1.2.1.2.2.1.3` | IF-MIB | `ethernetCsmacd(6)` para los 12 puertos (estándar `IANAifType-MIB`, no propietario). |
| `ifOperStatus`/`ifAdminStatus` | `1.3.6.1.2.1.2.2.1.8` / `...1.7` | IF-MIB | Los 12 puertos simulados están arriba (`up`); el puerto caído a propósito de esta simulación está en el servidor `hpe-dl360-01` (`MAPEO-SERVIDOR.md`), no en el chasis. |
| `ifSpeed`/`ifHighSpeed` | `1.3.6.1.2.1.2.2.1.5` / `1.3.6.1.2.1.31.1.1.1.15` | IF-MIB | 10 Gb por puerto (Flex-10/10D): `ifSpeed=4294967295` (tope de 32 bits, ya que 10 Gbps lo supera) y `ifHighSpeed=10000` (Mbps), mismo criterio que `cpqNicIfPhysAdapterSpeed`/`SpeedMbps` en el servidor. |
| Relación puerto → interfaz | `1.3.6.1.4.1.11.5.7.5.2.3.1.1.6.1.2` (`vcModulePortIfIndex`) — tabla `vcModulePortTable`, índice `vcModulePort` (`...6.1.1`) | HPVCMODULE-MIB | *"The value of the instance of the ifIndex object, defined in IF-MIB, for the interface corresponding to this port."* Se usa `vcModulePort` = `1`..`12` (mismo orden que los `ifIndex` de arriba) y `vcModulePortIfIndex` apuntando 1 a 1 a esos `ifIndex`. |

**Contadores de tráfico y errores que crecen:** `ifInOctets`/`ifOutOctets` (Counter32, tag `65`
en `.snmprec`) y `ifHCInOctets`/`ifHCOutOctets` (Counter64, tag `70`) de `ifXTable`, más
`ifInErrors`/`ifOutErrors` (Counter32, tag `65`), todos con variación `numeric` de snmpsim
(`<OID>|<tag>:numeric|rate=<por segundo>,initial=<valor>`) y una tasa distinta por cada uno de
los 12 puertos. A diferencia de `cpqnic.mib` en los servidores (que sólo tiene contadores de 32
bits, ver `MAPEO-SERVIDOR.md` sección 4.6), `ifXTable` sí trae la variante de 64 bits — por eso
la etiqueta `70` (Counter64) se ejercita acá, y la `65` (Counter32) tanto acá como en los
servidores.

## 5. Resumen de campos NO disponibles vía este MIB (no se inventan valores)

- `fabricante` (constante de aplicación, no OID — igual que el servidor)
- `generacion` de chasis (implícita en texto de `modelo`, sin campo propio — igual que el servidor)
- `velocidad_rpm` de ventiladores del chasis (la tabla de ventiladores del enclosure no tiene
  ningún campo de velocidad/RPM, a diferencia de la del servidor)
- `tipo_corriente` de fuentes de poder por unidad individual (existe un campo similar pero a
  nivel de todo el dominio de energía, no por PSU — ver sección 4.3)
- `marca` de tarjetas de red/interconnects (embebida en texto de `modelo`, sin campo aislado)
- `cantidad_puertos` de tarjetas de red/interconnects **como campo de `CPQRACK-MIB`**: sigue sin
  existir ese conteo en `cpqRackNetConnectorTable`. Sí es contable indirectamente a nivel de
  puerto individual vía `IF-MIB`/`HPVCMODULE-MIB` (sección 4.5) para el módulo de la bahía 1
  simulado en este chasis, pero eso no es un campo de `CPQRACK-MIB`.
- `estado` de tarjetas de red/interconnects como campo de salud/condición **de `CPQRACK-MIB`**:
  sigue sin existir en esa tabla (sólo presencia). `IF-MIB` (sección 4.5) sí aporta
  `ifOperStatus`/`ifAdminStatus` por puerto, que es un campo de estado distinto (de la interfaz,
  no de la condición de salud del módulo completo que pedía el mapeo original).

## 6. Campos generados por el ETL (ni SNMP ni manual)

- `ultima_actualizacion`: igual que para `Servidor` (ver sección 6 de `MAPEO-SERVIDOR.md`), no es
  un dato del chasis ni un valor que se lea de ningún OID ni que se llene a mano. La asigna el
  propio proceso de carga del ETL al momento de insertar o actualizar el registro en la base de
  datos, no se lee de ninguna fuente externa. No corresponde agregarlo a ningún `public.snmprec`.
