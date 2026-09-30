# Mapeo de campos de Storage (servidor + arreglo Fibre Channel) → OID reales

## 0. Nota sobre el origen de los archivos usados aquí

- `cpqfca.mib` (`CPQFCA-MIB`) y `cpqstsys.mib` (`CPQSTSYS-MIB`) ya estaban presentes en
  `mibs/hpe-real/` desde la copia inicial del subconjunto HPE/Compaq (ver sección 0 de
  [`MAPEO-SERVIDOR.md`](./MAPEO-SERVIDOR.md)); no se agregó nada nuevo a esa carpeta.
- Los campos de servidor (CPU, RAM, temperatura, consumo, ventiladores, fuentes,
  `version_firmware`, IP del SO, tarjetas Ethernet) **reutilizan exactamente** el mapeo ya
  resuelto en `MAPEO-SERVIDOR.md` (mismos OID que `data/hpe-dl380-01/public.snmprec`); no se
  volvieron a derivar.
- `NIMBLE-MIB` y `FCMGMT-MIB` **no** están en `mibs/hpe-real/` (no son MIB de Compaq/HPE). Se
  descargaron del repositorio público `github.com/librenms/librenms` con
  `git clone --filter=blob:none --sparse` + `git sparse-checkout` (rutas `mibs/nimble/NIMBLE-MIB`
  y `mibs/FCMGMT-MIB`) y se guardaron en `mibs/prestados/NIMBLE-MIB.mib` y
  `mibs/prestados/FCMGMT-MIB.mib` (con extensión `.mib` agregada para que `pysmi`/`snmpsim` los
  reconozcan; el contenido no se modificó). Esa carpeta se agregó como `--mib-source` adicional
  al compilar.
- Todos los OID numéricos de este documento se resolvieron compilando con `pysmi` y resolviendo
  los símbolos con `pysnmp` (`MibBuilder.importSymbols(...).getName()`), igual que en los demás
  mapeos de este repositorio.

## 1. Módulos identificados

| Archivo | Módulo ASN.1 real (línea `DEFINITIONS ::= BEGIN`) | Rol |
|---|---|---|
| `mibs/hpe-real/cpqfca.mib` | `CPQFCA-MIB` | Arreglo Fibre Channel externo: controladoras, discos físicos, volúmenes lógicos, HBA del host |
| `mibs/hpe-real/cpqstsys.mib` | `CPQSTSYS-MIB` | Chasis del sistema de almacenamiento externo (`cpqSsChassisTable`) |
| `mibs/prestados/NIMBLE-MIB.mib` | `NIMBLE-MIB` | **PRESTADO.** IOPS, latencia y capacidad usada (Nimble Storage, `enterprises.37447`) |
| `mibs/prestados/FCMGMT-MIB.mib` | `FCMGMT-MIB` | **PRESTADO/estándar de facto.** Fibre Alliance FC Management MIB, tráfico de puertos FC (`1.3.6.1.3.94`, rama `experimental`) |

Los servidores base (`cpqhlth`, `cpqhost`, `cpqstdeq`, `cpqsinfo`, `cpqnic`) ya están descritos
en `MAPEO-SERVIDOR.md` secciones 1-2 y no se repiten aquí.

## 2. Identidad general de la unidad Storage

El "servidor" (`hpe-storage-fc-01`/`02`) y el "arreglo" conectado se modelan en el **mismo
agente SNMP**, porque en la realidad `cpqfca`/`cpqstsys` los implementa el agente Insight
Manager instalado en el servidor host conectado por Fibre Channel al arreglo — no es un agente
separado. Por eso hay dos fuentes candidatas para varios campos generales, y hubo que decidir
cuál usar:

| Campo pedido | OID elegido | Módulo | Por qué esta fuente y no la otra |
|---|---|---|---|
| `hostname` | `1.3.6.1.4.1.232.11.2.2.12` (`cpqHoSystemName`) | CPQHOST-MIB (servidor) | El arreglo no tiene identidad de red propia (no resuelve por IP/DNS); el hostname real que expone la ficha es el del servidor host. `cpqSsChassisName` existe pero se usa solo como nombre informativo del chasis del arreglo (ver más abajo), no como `hostname`. |
| `numero_serie` | `1.3.6.1.4.1.232.8.2.2.1.1.3` (`cpqSsChassisSerialNumber`) | CPQSTSYS-MIB (arreglo) | Al contrario que el hostname, el número de serie de la ficha de **Storage** debe identificar la caja física del arreglo, no la del servidor (`cpqSiSysSerialNum` del servidor se sigue registrando por separado en la ficha de Servidor, no se reutiliza aquí). |
| `estado_operativo` | `1.3.6.1.4.1.232.8.2.2.1.1.11` (`cpqSsChassisOverallCondition`) | CPQSTSYS-MIB (arreglo) | Es la condición agregada del **chasis del arreglo** ("temperature, fans, power supplies... of the storage system"), más específica para Storage que `cpqHeMibCondition` del servidor. En la simulación, esta condición sube a "Degradado" en `hpe-storage-fc-01` por el disco degradado (ver sección 4), y queda "Encendido" en `hpe-storage-fc-02` porque el problema de esa unidad está en una fuente del **servidor**, no en el arreglo. |
| `modelo` | `1.3.6.1.4.1.232.8.2.2.1.1.26` (`cpqSsChassisProductId`) | CPQSTSYS-MIB (arreglo) | Texto libre del producto del arreglo (ej. `"HP StorageWorks MSA1000"`). Existe además `cpqSsChassisModel` (`...1.1.19`, enum categórico) que se usa como dato secundario/categórico. |
| `fabricante` | Constante de aplicación (`"HPE"`) | — | Igual que en servidores y switch: se deduce del prefijo `1.3.6.1.4.1.232` del `sysObjectID`, no hay OID de texto. |
| `generacion` | Regla del ETL sobre el texto de `modelo` del **servidor** (`cpqSiProductName`, ej. "Gen9") | CPQHOST-MIB (servidor) | Igual criterio que `MAPEO-SERVIDOR.md`: sin campo discreto: implícito en el texto del modelo de servidor. |
| `ubicacion` | `1.3.6.1.2.1.1.6.0` (`sysLocation`) | SNMPv2-MIB | Estándar; distinta entre las dos unidades simuladas. |
| `ip_gestion` | `1.3.6.1.2.1.4.20.1.1` (`ipAdEntAddr`) | IP-MIB estándar | Igual patrón que `MAPEO-SERVIDOR.md` sección 3: es la IP del servidor host, el arreglo no tiene IP propia. |
| `version_firmware` | `1.3.6.1.4.1.232.1.2.6.1` (`cpqSeSysRomVer`) | CPQSTDEQ-MIB (servidor) | Reutilizado tal cual de `MAPEO-SERVIDOR.md`; es la ROM del servidor. El arreglo sí tiene firmware propio por componente (`cpqFcaCntlrFWRev`, `cpqFcaHostCntlrFirmwareVersion`), pero no hay un "firmware del arreglo completo" único — se documenta esto como matiz, igual que en el servidor. |
| `temperatura`, `consumo_electico_w` | Igual que `MAPEO-SERVIDOR.md` (`cpqHeTemperatureCelsius`, `cpqHePowerMeterCurrReading`) | CPQHLTH-MIB (servidor) | Ver nota de limitación en sección 8: el arreglo externo (MSA1000/EVA) no tiene sensores propios en este paquete de MIB; se reutilizan los del servidor que lo administra. |
| `protocolo_comunicacion` | Constante de aplicación (`"Fibre Channel"`) | — | No hay un OID que declare el protocolo; es una propiedad conocida de antemano del tipo de arreglo modelado. |
| `capacidad_total_TB` | Suma de `cpqFcaPhyDrvSize` (MB) de todos los discos del arreglo | CPQFCA-MIB | Ver regla de coherencia en sección 4.3. |
| `capacidad_usada_TB` | **PRESTADO** (NIMBLE-MIB `diskVolBytesUsedLow/High` + `diskSnapBytesUsedLow/High`) | NIMBLE-MIB | Ver sección 9. |
| `iops` | **Manual/nominal.** Ver sección 11. | — | La única columna de IOPS en estos MIB (`arubaWired...` no aplica aquí; en `CPQFCA-MIB`/`CPQSTSYS-MIB` no existe ningún objeto de IOPS soportadas o medidas) no existe; el IOPS medido en vivo sale de NIMBLE-MIB (PRESTADO, sección 9) y va a métrica histórica, no a este campo nominal. |

## 3. `estado_operativo`: enums involucrados y su traducción

En Storage confluyen **tres** condiciones distintas de HPE, cada una con su propio enum
`other/ok/degraded/failed` (idéntico patrón numérico en los tres, pero objetos distintos):

| Objeto | Tabla | Qué mide |
|---|---|---|
| `cpqSsChassisOverallCondition` | `cpqSsChassisTable` (arreglo) | Condición agregada del chasis del arreglo — la que se usa para `estado_operativo` de Storage (sección 2). |
| `cpqFcaCntlrCondition` | `cpqFcaCntlrTable` (arreglo) | Condición de la controladora RAID del arreglo — se usa para `estado` de `controladorasRAID` (sección 4.2). |
| `cpqFcaPhyDrvCondition` | `cpqFcaPhyDrvTable` (arreglo) | Condición de cada disco físico del arreglo — se usa para `estado` de `discos` (sección 4.1). |
| `cpqFcaHostCntlrCondition` | `cpqFcaHostCntlrTable` (servidor) | Condición de la tarjeta HBA Fibre Channel del servidor — se usa para `estado` de la tarjeta FC (sección 5.2). |

Traducción a `EstadoEnum` (misma tabla que `MAPEO-SERVIDOR.md` sección 2, para los cuatro
objetos de arriba):

| Valor origen HPE | `EstadoEnum` |
|---|---|
| `ok(2)` | **Encendido** |
| `other(1)`, `degraded(3)` | **Degradado** |
| `failed(4)` | **Apagado** |

`cpqFcaPhyDrvStatus` (estado operacional más detallado del disco: `unconfigured/ok/
threshExceeded/predictiveFailure/failed/unsupportedDrive`) es un objeto **distinto** de
`cpqFcaPhyDrvCondition`; se documenta pero no se usa para `EstadoEnum` (se deja como dato
adicional, igual que `cpqNicIfPhysAdapterStatus` vs. `cpqNicIfPhysAdapterCondition` en
`MAPEO-SERVIDOR.md` sección 4.6).

## 4. Almacenamiento

### 4.1 `discos` (`CPQFCA-MIB`, tabla `cpqFcaPhyDrvTable`, índices `cpqFcaPhyDrvBoxIndex`+`cpqFcaPhyDrvIndex`)

**No se usa `cpqDaPhyDrv` (CPQIDA-MIB) para este campo.** `cpqDaPhyDrv` sigue existiendo en el
`.snmprec` de cada unidad, pero reducido a los 2 discos internos de arranque del servidor (RAID1,
ver sección 6) — son un concepto distinto (discos internos del servidor host, no del arreglo
externo) y no se exponen en la ficha de Storage.

| Campo | OID (columna) | Notas |
|---|---|---|
| `marca` | **Sin OID propio.** Va embebida como texto libre dentro de `modelo` (`cpqFcaPhyDrvModel`, ej. "HP 900GB..."), regla del ETL — mismo criterio que discos/RAM/tarjetas del servidor. |
| `modelo` | `1.3.6.1.4.1.232.16.2.5.1.1.3` (`cpqFcaPhyDrvModel`) | DisplayString, texto libre del fabricante+modelo del disco. |
| `tipo` | `1.3.6.1.4.1.232.16.2.5.1.1.51` (`cpqFcaPhyDrvType`) | Enum `other/parallelScsi/sata/sas`. |
| `capacidad_GB` | `1.3.6.1.4.1.232.16.2.5.1.1.38` (`cpqFcaPhyDrvSize`) | INTEGER en MB (mismo criterio 2^20 que `cpqDaPhyDrvSize` del servidor) → convertir a GB. |
| `velocidad_rpm` | `1.3.6.1.4.1.232.16.2.5.1.1.50` (`cpqFcaPhyDrvRotationalSpeed`) | Enum categórico `other/rpm7200/rpm10K/rpm15K` (no incluye SSD, a diferencia del enum del servidor) — mapear a un RPM representativo, regla del ETL. |
| `estado` | `1.3.6.1.4.1.232.16.2.5.1.1.31` (`cpqFcaPhyDrvCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum (ver sección 3). En `hpe-storage-fc-01`, el disco 6 (`Bay 6`) está en `degraded(3)` a propósito (regla 4 del enunciado). |
| numero de serie (no pedido en la ficha pero disponible) | `1.3.6.1.4.1.232.16.2.5.1.1.43` (`cpqFcaPhyDrvSerialNum`) | Se pobló igual, útil para trazabilidad aunque no esté en la lista de campos pedidos. |
| Bahía | `1.3.6.1.4.1.232.16.2.5.1.1.5` (`cpqFcaPhyDrvBay`) | Se usa como identificador de posición física del disco dentro del arreglo. |
| Sectores leídos/escritos | `cpqFcaPhyDrvReads`/`HReads` (`...1.1.10`/`...1.1.9`) y `Writes`/`HWrites` (`...1.1.12`/`...1.1.11`) | Contadores de 32 bits partidos en dos (bajo/alto): el valor real = `HReads * 2^32 + Reads`. **No son operaciones de E/S (IOPS)**, son sectores acumulados desde el último reinicio del contador de referencia — no sirven para calcular IOPS. Se poblaron con valores estáticos plausibles (parte alta en 0, ya que ningún disco simulado acumula más de 2^32 sectores); no se les exige que crezcan porque el enunciado no lo pide para este objeto específicamente (a diferencia de NIMBLE-MIB/FCMGMT-MIB, que sí deben crecer). |

### 4.2 `controladorasRAID` (`CPQFCA-MIB`, tabla `cpqFcaCntlrTable`, índices `cpqFcaCntlrBoxIndex`+`cpqFcaCntlrBoxIoSlot`)

| Campo | OID (columna) | Notas |
|---|---|---|
| `modelo` | `1.3.6.1.4.1.232.16.2.2.1.1.3` (`cpqFcaCntlrModel`) | Enum de modelos de arreglo (`fibreArray/msa1000/hsg80/hsv110/msa500G2/...`), no texto libre. `hpe-storage-fc-01` usa `msa1000(3)`; `hpe-storage-fc-02` usa `hsv110(6)` (controladora de una Enterprise Virtual Array). |
| `numero_serie` | `1.3.6.1.4.1.232.16.2.2.1.1.9` (`cpqFcaCntlrSerialNumber`) | DisplayString. |
| `estado` | `1.3.6.1.4.1.232.16.2.2.1.1.6` (`cpqFcaCntlrCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum (ver sección 3). |
| `raid` | `1.3.6.1.4.1.232.16.2.3.1.1.3` (`cpqFcaLogDrvFaultTol`) — tabla `cpqFcaLogDrvTable`, relacionada vía `cpqFcaLogDrvBoxIndex` | El nivel RAID es propiedad del **volumen lógico**, no de la controladora (mismo matiz que `cpqDaLogDrvFaultTol` en `MAPEO-SERVIDOR.md` sección 4.7): se toma el volumen lógico del arreglo como representativo. Enum: `other/none/mirroring/dataGuard/distribDataGuard/advancedDataGuard` (nota: el valor `6` no está definido en este MIB — salta de `5` a `7`). |
| Firmware (no pedido en la ficha, disponible) | `1.3.6.1.4.1.232.16.2.2.1.1.4` (`cpqFcaCntlrFWRev`) | Se pobló igual. |
| WWN (no pedido, disponible) | `1.3.6.1.4.1.232.16.2.2.1.1.8` (`cpqFcaCntlrWorldWideName`) | Identificador Fibre Channel de la controladora. |

### 4.3 Regla de coherencia de capacidades (regla 2 del enunciado)

1. **`capacidad_total_TB`** = suma de `cpqFcaPhyDrvSize` (MB) de **todos** los discos físicos
   del arreglo, sin ajustar por RAID.
2. **Capacidad útil máxima** (no es un campo de la ficha, es un límite intermedio que el ETL
   debe calcular para validar que el volumen lógico es plausible) se deriva de
   `cpqFcaLogDrvFaultTol` sobre el total de discos `n`, regla propuesta y documentada aquí
   (no hay un objeto SNMP que la calcule):

   | `cpqFcaLogDrvFaultTol` | Regla de capacidad útil |
   |---|---|
   | `none(2)` | 100% del total bruto |
   | `mirroring(3)` | 50% del total bruto (se asume que los `n` discos forman pares espejados; el MIB no distingue RAID1 simple de RAID10, así que esta regla cubre ambos casos de forma conservadora) |
   | `dataGuard(4)` / `distribDataGuard(5)` | `(n-1)/n` del total bruto (equivalente a RAID 4/5: un disco de paridad) |
   | `advancedDataGuard(7)` | `(n-2)/n` del total bruto (equivalente a RAID 6: dos discos de paridad) |

3. **`cpqFcaLogDrvSize`** (el volumen lógico real reportado por el arreglo) debe ser **menor o
   igual** a esa capacidad útil máxima. Verificado en ambas unidades (ver salida de
   `data/verify_agents.py` / script de generación):
   - `hpe-storage-fc-01`: 6 discos × 858 495 MB = 5 150 970 MB brutos; RAID `distribDataGuard`
     (RAID5) → útil máx. = 4 292 475 MB; volumen lógico simulado = 4 000 000 MB ✅.
   - `hpe-storage-fc-02`: 8 discos × 571 776 MB = 4 574 208 MB brutos; RAID `mirroring` → útil
     máx. = 2 287 104 MB; volumen lógico simulado = 2 000 000 MB ✅.
4. **`capacidad_usada_TB`** (PRESTADO, NIMBLE-MIB, sección 9) debe ser **menor o igual** al
   volumen lógico (`cpqFcaLogDrvSize`), no a la capacidad bruta ni a la útil máxima:
   - `hpe-storage-fc-01`: usada = 2 000 000 MB ≤ volumen lógico 4 000 000 MB ✅.
   - `hpe-storage-fc-02`: usada = 1 200 000 MB ≤ volumen lógico 2 000 000 MB ✅.

## 5. Tarjetas de red

### 5.1 Ethernet (`CPQNIC-MIB`, servidor) — reutilizado tal cual de `MAPEO-SERVIDOR.md` sección 4.6

Mismas columnas de `cpqNicIfPhysAdapterTable` (MAC `...1.1.4`, velocidad `...1.1.33`/`...1.1.36`,
estado `...1.1.14`, tráfico `...1.1.37`/`...1.1.38`, errores `...1.1.18`/`...1.1.19`/`...1.1.20`/
`...1.1.21`), con contadores creciendo vía variación `numeric` (Counter32, tag `65`), igual que en
`hpe-dl380-01`. No se usa `IF-MIB` para esto (instrucción explícita del enunciado).

### 5.2 Fibre Channel (`CPQFCA-MIB`, tabla `cpqFcaHostCntlrTable`, índice `cpqFcaHostCntlrIndex`)

Esta tabla describe la **tarjeta HBA Fibre Channel del servidor** (el "iniciador" que se conecta
al arreglo), no un puerto del arreglo en sí.

| Campo | OID (columna) | Notas |
|---|---|---|
| `marca` (tarjeta) | Constante de aplicación (`"HPE"`) | Igual que Ethernet: no hay campo de fabricante aislado. |
| `modelo` (tarjeta) | `1.3.6.1.4.1.232.16.2.7.1.1.3` (`cpqFcaHostCntlrModel`) | Enum categórico con decenas de modelos reales de HBA HPE/Emulex/QLogic (`fca-lpe1605`, `fca-sn1600e-2p`, etc.), no texto libre. Se usó `fca-lpe1605(58)` en `hpe-storage-fc-01` y `fca-sn1600e-2p(85)` en `hpe-storage-fc-02`; el ETL debe mapear el enum a un nombre comercial (tabla de catálogo, no viene como texto desde el MIB). |
| `cantidad_puertos` | **No disponible como conteo en este MIB.** Cada fila de `cpqFcaHostCntlrTable` ya representa una controladora HBA completa, no puertos individuales; no hay una sub-tabla de puertos de la HBA en `CPQFCA-MIB`. Se simuló 1 fila = 1 HBA con 1 puerto reportado. |
| `estado` (tarjeta) | `1.3.6.1.4.1.232.16.2.7.1.1.5` (`cpqFcaHostCntlrCondition`) | Enum `other/ok/degraded/failed` → EstadoEnum (ver sección 3). |
| `numero_puerto` | `1.3.6.1.4.1.232.16.2.7.1.1.2` (`cpqFcaHostCntlrSlot`) | **Decisión de mapeo:** se usa el número de slot PCI de la HBA como identificador de "puerto" ante la ausencia de una tabla de puertos dedicada (ver punto anterior). |
| `mac_address` | `1.3.6.1.4.1.232.16.2.7.1.1.12` (`cpqFcaHostCntlrWorldWidePortName`, WWPN) | **Decisión de mapeo:** Fibre Channel no usa direcciones MAC; se usa el **WWPN** (World Wide Port Name, identificador único de puerto FC de 8 bytes, aquí representado como 16 caracteres hexadecimales) como equivalente funcional en el campo `mac_address` de la ficha. Documentar esta sustitución es obligatorio para no confundirlo con una MAC Ethernet real. |
| `velocidad` | **Sin OID.** `CPQFCA-MIB` no expone la velocidad de enlace FC negociada (a diferencia de `cpqNicIfPhysAdapterSpeed` en Ethernet); no se inventó. | |
| Firmware (no pedido, disponible) | `1.3.6.1.4.1.232.16.2.7.1.1.13` (`cpqFcaHostCntlrFirmwareVersion`) | Se pobló igual. |
| WWNN (no pedido, disponible) | `1.3.6.1.4.1.232.16.2.7.1.1.6` (`cpqFcaHostCntlrWorldWideName`) | Node name (distinto del WWPN/port name usado arriba). |

## 6. CPU y RAM — reutilizado tal cual de `MAPEO-SERVIDOR.md` secciones 4.1 y 4.3

Mismos OID de `CPQSTDEQ-MIB` (`cpqSeCpuTable`/`cpqSeCpuCacheTable`) y `CPQSINFO-MIB`
(`cpqSiMemModuleTable`) que en los servidores standalone; los valores (marca, familia/nombre,
GHz, núcleos, `cantidad_hilos = cantidad_nucleos × cpqSeCPUCoreMaxThreads`, cachés L1/L2/L3,
manufacturer/part number/serie/MHz/capacidad de RAM) se ajustaron por unidad (CPU Xeon E5 v3/v4
de generación Gen9, acorde al servidor simulado). RAID interno de arranque (`CPQIDA-MIB`) se
redujo a 1 controladora + 1 volumen lógico RAID1 + **2 discos** únicamente (instrucción del
enunciado: "el DL base solo conserva 2 discos internos de arranque en cpqida" — ese RAID interno
no se expone en la ficha de Storage, ver sección 4.1).

`marca`/`modelo` de RAM y `marca` de CPU: sin OID de fabricante propio del "conjunto" (solo por
componente/DIMM individual), igual matiz que en `MAPEO-SERVIDOR.md`.

## 7. Ventiladores y fuentes — reutilizado tal cual de `MAPEO-SERVIDOR.md` secciones 4.4 y 4.5

Mismos OID de `CPQHLTH-MIB` (`cpqHeFltTolFanTable`, `cpqHeFltTolPowerSupplyTable`). En
`hpe-storage-fc-02`, la fuente 2 (`Bay 2`) está en `failed(4)` a propósito
(`cpqHeFltTolPowerSupplyCondition`, regla 4 del enunciado) — nótese que este campo vive en
`...6.2.9.3.1.4`, **no** en `...6.2.9.3.1.9` (columna que existe en la misma tabla pero con otro
significado no documentado por el MIB; se verificó la posición exacta contra
`MAPEO-SERVIDOR.md` antes de escribir el `.snmprec`, ya que es un error fácil de cometer por la
cantidad de columnas casi-idénticas de esta tabla).

`modelo` de ventiladores: sin OID (mismo hueco que en servidores, `CPQHLTH-MIB` no tiene nombre
comercial de ventilador). `tipo_corriente` de fuentes: sin OID (mismo hueco).

## 8. Nota de limitación importante

**CPU, RAM, temperatura, consumo eléctrico, ventiladores, fuentes de poder y tarjetas de red
Ethernet de la ficha de Storage son, en esta simulación, los del *servidor* que administra el
arreglo — no del arreglo externo en sí.** Esto es una limitación real del paquete de MIB
disponible, no una decisión arbitraria: ni `CPQFCA-MIB` ni `CPQSTSYS-MIB` exponen sensores de
temperatura, medidor de consumo, tabla de ventiladores, tabla de fuentes de poder propia del
gabinete del arreglo, ni tarjetas de red Ethernet del arreglo (un MSA1000/EVA se gestiona
íntegramente a través del servidor host vía Fibre Channel, sin una interfaz de red Ethernet
propia en este modelo de MIB). Si en el futuro se simula un arreglo con su propia gestión
Ethernet (ej. un MSA2000/P2000 con módulo de gestión IP dedicado), haría falta un MIB adicional
no incluido en este trabajo.

## 9. `capacidad_usada_TB`, IOPS y latencia — PRESTADO (`NIMBLE-MIB`, `globalStats`)

> ⚠️ **PRESTADO (MIB de otro equipo, no lo expone un servidor con arreglo real).**
> `NIMBLE-MIB` (`enterprises.37447`) es el MIB propietario de Nimble Storage (adquirida por HPE
> en 2017, pero con una línea de producto y un MIB completamente distintos de MSA/EVA). Se usa
> aquí únicamente porque ni `CPQFCA-MIB` ni `CPQSTSYS-MIB` exponen IOPS, latencia ni capacidad
> usada en bytes. **El ETL debe poder ignorar este bloque al consultar un servidor+arreglo HPE
> real** (esos OID no existirán). En `public.snmprec` este bloque está marcado con un comentario
> `#` y agrupado (ver nota de formato más abajo).

Tabla `globalStats` (escalares, no indexados por instancia — un solo arreglo virtual por agente):

| Campo | OID | Tipo/notas |
|---|---|---|
| `capacidad_usada_TB` | `diskVolBytesUsedLow`/`High` (`.12`/`.13`) + `diskSnapBytesUsedLow`/`High` (`.14`/`.15`) | `Unsigned32` cada uno (no Counter: es una foto del estado actual, no una variación `numeric`). Valor real en bytes = `High * 2^32 + Low`; `capacidad_usada` = volúmenes + snapshots. Calculado explícitamente con división/módulo enteros por 2^32 en el script de generación, no aproximado. |
| IOPS lectura/escritura acumuladas | `ioReads`/`ioWrites` (`.2`/`.4`) | `Counter64` (tag `70`), variación `numeric` de snmpsim — **debe crecer**. |
| Bytes leídos/escritos acumulados | `ioReadBytes`/`ioWriteBytes` (`.8`/`.10`) | `Counter64`, `numeric` — debe crecer. |
| Microsegundos acumulados en E/S | `ioReadTimeMicrosec`/`ioWriteTimeMicrosec` (`.6`/`.7`) | `Counter64`, `numeric` — debe crecer. |

**Cálculo de IOPS/latencia/throughput a partir de dos lecturas** (lo que hace
`data/verify_agents.py`): con `Δreads`, `Δwrites`, `Δreadtime`, `Δwritetime`, `Δreadbytes`,
`Δwritebytes` entre dos GET separados por `Δt` segundos,

```
IOPS_lectura   = Δreads / Δt
IOPS_escritura = Δwrites / Δt
latencia_lectura_ms   = (Δreadtime / Δreads) / 1000     (si Δreads > 0)
latencia_escritura_ms = (Δwritetime / Δwrites) / 1000   (si Δwrites > 0)
throughput_lectura_MBs   = Δreadbytes / Δt / 1048576
throughput_escritura_MBs = Δwritebytes / Δt / 1048576
```

Tasas elegidas (`rate=` de la variación `numeric`) y resultado esperado de esas fórmulas:

| Unidad | IOPS lectura | IOPS escritura | Latencia lectura | Latencia escritura | Throughput lectura | Throughput escritura |
|---|---|---|---|---|---|---|
| `hpe-storage-fc-01` | ~1200 | ~800 | ~1.2 ms | ~2.5 ms | ~37.5 MB/s | ~50 MB/s |
| `hpe-storage-fc-02` | ~600 | ~400 | ~0.8 ms | ~1.8 ms | ~9.4 MB/s | ~12.5 MB/s |

Verificado en vivo con `data/verify_agents.py` (dos GET separados 5 s): ambas unidades
reprodujeron estos valores dentro de un margen de ruido de redondeo esperable, y las cuatro
latencias cayeron dentro del rango realista pedido (0.5–5 ms).

## 10. Tráfico Fibre Channel — PRESTADO (`FCMGMT-MIB`, `connUnitPortStatTable`)

> ⚠️ **PRESTADO (MIB de otro equipo, no lo expone un servidor con arreglo real).** `FCMGMT-MIB`
> (Fibre Alliance FC Management MIB, `1.3.6.1.3.94`) es un estándar de facto de la industria SAN
> (Brocade, McData, etc.), no un MIB de HPE/Compaq. Se usa porque ni `CPQFCA-MIB` ni
> `CPQSTSYS-MIB` exponen contadores de tráfico por puerto FC.

Tabla `connUnitPortStatTable`, índice `{connUnitPortStatUnitId (FcGlobalId, OCTET STRING de 16
bytes fijos → 16 sub-identificadores de OID, sin prefijo de longitud), connUnitPortStatIndex}`.
Se modelaron 2 puertos (`connUnitPortStatIndex = 1, 2`) del **arreglo** (lado destino/target de
la fábrica FC, distinto de la HBA del servidor de la sección 5.2, que es el lado iniciador), bajo
un `connUnitId` sintético de 16 bytes derivado del WWN de la controladora (no se modeló la tabla
`connUnitTable` completa, solo el índice necesario para `connUnitPortStatTable`).

| Campo | OID (columna) | Notas |
|---|---|---|
| `connUnitPortStatCountTxObjects`/`RxObjects` | `.4`/`.5` | Tramas (frames) transmitidas/recibidas. |
| `connUnitPortStatCountTxElements`/`RxElements` | `.6`/`.7` | Octetos (bytes) transmitidos/recibidos. |

**Limitación de la variación `numeric` de snmpsim — verificada, no supuesta:** los cuatro
objetos anteriores están definidos en el MIB como `OCTET STRING (SIZE (8))`, no como
`Counter32`/`Counter64` nativos de SMIv2. Se inspeccionó el código fuente de
`snmpsim/variation/numeric.py` (función `record()`, constante `INTEGER_TYPES`): el módulo
`numeric` solo opera sobre los tipos ASN.1 `Counter32`, `Counter64`, `Gauge32`, `TimeTicks` e
`Integer`; para cualquier otro tipo (incluido `OCTET STRING`) el propio recorder de snmpsim
devuelve el valor crudo sin aplicar variación, y `snmpsim/grammar/snmprec.py` (`TAG_MAP`) tampoco
registra ninguna etiqueta numérica para `OCTET STRING`. Es decir: **estos cuatro contadores no
pueden crecer con `numeric` en snmpsim tal como está definido el MIB**, y no es un caso de "no
lo intenté" — se confirmó leyendo el código del módulo antes de decidir la alternativa. Se
usaron valores **fijos en hexadecimal** (tag `4x`, 16 caracteres = 8 bytes, big-endian) en su
lugar, documentado aquí como limitación explícita de la simulación (a diferencia de
`ifHCInOctets`/`ifHCOutOctets` en `IF-MIB`, que sí son `Counter64` nativos y sí crecen en los
agentes de switch/chasis de este mismo repositorio).

**Nota de formato del `.snmprec`:** `NIMBLE-MIB` (`1.3.6.1.4.1.37447`) y `FCMGMT-MIB`
(`1.3.6.1.3.94`) quedan en dos regiones numéricamente muy separadas del árbol de OID (94 < 232 <
37447), así que en un archivo `.snmprec` ordenado por OID —imprescindible para que snmpsim
resuelva bien `GETNEXT`/`walk`; se verificó que snmpsim indexa el archivo en el orden en que las
líneas aparecen en el texto (`snmpsim/record/search/database.py`, función `create()`), sin
volver a ordenarlas— nunca pueden quedar uno junto al otro. Cada bloque PRESTADO queda agrupado
y marcado con su propio comentario (`# BLOQUE PRESTADO ... FCMGMT-MIB` / `... NIMBLE-MIB`), lo
que ya permite ubicar y quitar cada uno con un solo bloque de comentario. `snmpsim` ignora las
líneas en blanco y las que empiezan con `#` (mismo mecanismo verificado y usado en
`data/aruba-cx-sw01/public.snmprec`).

## 11. Campo `iops` (nominal) — manual, no SNMP

La ficha pide un campo `iops` a nivel de Detalle General de Storage. Ni `CPQFCA-MIB` ni
`CPQSTSYS-MIB` exponen un valor de IOPS soportadas/nominales del arreglo (solo hay contadores de
sectores por disco, sección 4.1, que no son IOPS). Interpretación adoptada: este campo es el
**IOPS nominal del fabricante** (dato de ficha técnica/catálogo, ej. "hasta N IOPS soportadas
según el fabricante"), **manual**, cargado una vez al alta del equipo — no se lee de SNMP y no
cambia con el uso. La medición de IOPS **en vivo** (sección 9) es un dato completamente distinto
que va a métrica histórica (serie temporal), no a este campo nominal de la ficha.

## 12. Campos sin fuente directa (no se inventan OID ni valores)

| Campo | Motivo |
|---|---|
| `marca` de discos, RAM y tarjetas de red | Va dentro del texto de `modelo`; regla del ETL, sin campo de fabricante aislado (igual que en servidores). |
| `generacion` de RAM (DDR3/4/5) | `cpqSiMemModuleTechnology` es tecnología legacy, no DDR (mismo hueco que en servidores). |
| `tipo_corriente` de fuentes de poder | `CPQHLTH-MIB` no expone AC/DC por fuente individual (mismo hueco que en servidores). |
| `serie` de tarjetas de red y de ventiladores | Ningún objeto de `CPQNIC-MIB`/`CPQHLTH-MIB`/`CPQFCA-MIB` expone número de serie de tarjeta de red ni de ventilador. |
| `modelo` de ventiladores | `CPQHLTH-MIB` no tiene nombre comercial de ventilador (mismo hueco que en servidores). |
| `velocidad` de la tarjeta/puerto Fibre Channel | `CPQFCA-MIB` no expone la velocidad de enlace negociada de la HBA. |
| `cantidad_puertos` de la tarjeta Fibre Channel | `cpqFcaHostCntlrTable` modela una HBA completa por fila, sin sub-tabla de puertos. |

## 13. Campos generados por el ETL (ni SNMP ni manual)

- `ultima_actualizacion`: igual que en `MAPEO-SERVIDOR.md` sección 6 y `MAPEO-CHASIS.md`
  sección 6: la asigna el proceso de carga del ETL al insertar/actualizar el registro, no se lee
  de ningún OID ni se llena a mano. No corresponde agregarlo a ningún `public.snmprec`.
- `cantidad_puertos` de tarjetas de red Ethernet, `cantidad_hilos` de CPU: mismas reglas
  derivadas (no de un único OID) que `MAPEO-SERVIDOR.md` secciones 4.1 y 4.6.
