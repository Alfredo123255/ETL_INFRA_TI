# Cobertura de metadatos para un switch ArubaOS-CX

## Resultado

El paquete permite construir un agente simulado con identificación, puertos, tráfico, errores, temperatura, consumo, ventiladores y fuentes. No permite completar por sí solo todos los metadatos físicos de CPU y módulos RAM definidos en el documento.

Esta revisión verifica definiciones de objetos en los archivos locales, no respuestas de un switch real. La presencia de un MIB no garantiza que todos los modelos implementen sus objetos. No se han compilado ni validado aquí todos los OID numéricos ni las dependencias del paquete.

## Fuentes y alcance

- Documento de referencia: `20220825_AlfredoSanchez_CesarAguilera_E1 (9) (3) (3).docx`; tablas de activos, switches, puerto_switch, CPU, RAM, fuentes de poder y ventiladores.
- Paquete: [ALL-Supported-MIBs](./ALL-Supported-MIBs/), procedente de `ArubaOS-CX_10.16.1000_MIBs_15th_May2025`.
- El [Readme original](./ALL-Supported-MIBs/Readme.txt) identifica la versión como 10.16.1000 Halon y su actualización como 12 de marzo de 2025. El nombre de la carpeta de descarga contiene otra fecha; no se interpreta como fecha del firmware instalado.
- Los nombres de objetos siguientes se comprobaron en los MIB. Antes de generar registros SNMP deben resolverse sus OID, tipos e índices desde esos archivos.

## Cobertura de la ficha

| Metadato | Fuente real | Origen y tratamiento |
|---|---|---|
| hostname | SNMPv2-MIB: sysName | OID estándar. |
| numero_serie, fabricante, modelo | ENTITY-MIB: entPhysicalSerialNum, entPhysicalMfgName, entPhysicalModelName | OID estándar; seleccionar la entidad física del chasis, no cualquier componente. |
| version_firmware | ENTITY-MIB: entPhysicalFirmwareRev, entPhysicalSoftwareRev | OID estándar; distinguir firmware de software ArubaOS-CX y comprobar qué informa el equipo. |
| Imágenes de software almacenadas | ARUBAWIRED-SWITCH-IMAGE-MIB: arubaWiredSwitchImageVersion | OID propietario; una imagen almacenada o de arranque predeterminado no prueba cuál está ejecutándose. |
| numero_puerto | IF-MIB: ifName | OID estándar; conservar nombres como identificadores de interfaz. |
| velocidad | IF-MIB: ifHighSpeed | OID estándar, expresado en millones de bits por segundo. |
| Estado del puerto | IF-MIB: ifAdminStatus, ifOperStatus | OID estándar más normalización del ETL; conservar la diferencia entre estado administrativo y operativo. |
| Tráfico | IF-MIB: ifHCInOctets, ifHCOutOctets | Counter64. Para tasas, calcular diferencias entre muestras y manejar reinicios/discontinuidades. |
| Errores | IF-MIB: ifInErrors, ifOutErrors | Counter32; manejar desbordamiento y reinicios al calcular diferencias. |
| cantidad_puertos | IF-MIB y ENTITY-MIB | Regla ETL: contar solo puertos físicos dentro del alcance definido. No usar ifNumber sin filtrado. Excluir interfaces virtuales y agregaciones. |
| cantidad_puertos_ocupados y libres | Estado de interfaces | Regla ETL parcial: contar enlaces activos/inactivos no demuestra disponibilidad administrativa del puerto. |
| temperatura | ARUBAWIRED-TEMPSENSOR-MIB: arubaWiredTempSensorTemperature | OID propietario, milésimas de Celsius; dividir entre 1000 y definir el sensor representativo. |
| consumo_electrico_w | ARUBAWIRED-POWER-STAT-MIB: arubaWiredPowerStatPowerConsumed | OID propietario en W; usar la fila del componente chasis para el total. No sumar total y componentes. |
| Ventilador: modelo | ARUBAWIRED-FAN-MIB: arubaWiredFanProductName | OID propietario. |
| Ventilador: numero_serial | ARUBAWIRED-FAN-MIB: arubaWiredFanSerialNumber | OID propietario. |
| Ventilador: velocidad_rpm | ARUBAWIRED-FAN-MIB: arubaWiredFanRPM | OID propietario. |
| Ventilador: estado | ARUBAWIRED-FAN-MIB: arubaWiredFanStateEnum | OID propietario más normalización de sus propios valores. |
| Fuente: modelo y numero_serial | ARUBAWIRED-POWERSUPPLY-MIB: arubaWiredPSUProductName, arubaWiredPSUSerialNumber | OID propietario. |
| Fuente: potencia instantánea | ARUBAWIRED-POWERSUPPLY-MIB: arubaWiredPSUInstantaneousPower | Potencia suministrada en W; no confundir con potencia máxima ni con consumo de entrada. |
| Fuente: capacidad máxima | ARUBAWIRED-POWERSUPPLY-MIB: arubaWiredPSUMaximumPower | Capacidad máxima suministrable en W. |
| Fuente: estado | ARUBAWIRED-POWERSUPPLY-MIB: arubaWiredPSUStateEnum | OID propietario más normalización de sus propios valores. |
| Uso de CPU y RAM | ARUBAWIRED-SYSTEMINFO-MIB: arubaWiredSystemInfoCpu, arubaWiredSystemInfoMemory | Porcentajes por subsistema; no describen procesadores ni DIMM individuales. |
| Memoria total y usada | HOST-RESOURCES-MIB: hrMemorySize, hrStorageSize, hrStorageUsed, hrStorageAllocationUnits | Objetos estándar candidatos; confirmar implementación, tipo de almacenamiento y unidades. No equivalen a capacidad por DIMM. |

## Campos sin fuente directa o con origen externo

| Campo | Resultado |
|---|---|
| CPU: familia, marca, modelo, GHz, núcleos, hilos y cachés L1/L2/L3 | No se encontró una fuente específica que complete este inventario físico. No inferirlo del uso de CPU. |
| CPU: serie y estado individual | No se confirmó una fuente por procesador. ENTITY-MIB podría aportar inventario si el equipo publica esas entidades; requiere comprobación real. |
| RAM: serie, marca, modelo, DDR, MHz, capacidad y salud por módulo | No se encontró una tabla específica por DIMM equivalente a la de HPE. No inventar módulos a partir de memoria total. |
| Fuente: tipo_corriente AC/DC | Sin columna explícita encontrada en ARUBAWIRED-POWERSUPPLY-MIB; usar catálogo validado o dejar sin fuente. El tipo de un sensor eléctrico no determina por sí solo el tipo de entrada de una PSU. |
| tipo_red | Manual: función organizacional, por ejemplo LAN Core. |
| modo_operacion | Manual o catálogo validado: clasificación LAN/SAN del documento. No equivale a dúplex ni autonegociación. |
| generacion | Catálogo o normalización documentada del modelo; sin fuente discreta confirmada. |
| ubicacion | sysLocation aporta texto configurado; conciliar con el datacenter del catálogo. |
| responsable | sysContact aporta contacto configurado, sujeto a conciliación; alternativa manual. |
| ip_gestion | Configuración del destino de monitoreo; IP-MIB puede listar direcciones, pero no identifica automáticamente la IP de gestión elegida. |
| cluster/proyecto, ambiente, orden_compra, fecha_eol, fecha_eos | Manual o catálogo externo. No se obtienen de los objetos revisados. |
| mantenimiento_activo y Baja | Gestión administrativa explícita. |
| estado_operativo | Regla ETL basada en salud y conectividad. Un timeout no demuestra apagado. No confundir estado del switch con estado de sus puertos. |
| ultima_actualizacion | Fecha de carga/actualización asignada por el ETL. |
| Fecha de instalación de firmware | Sin fuente confirmada. arubaWiredSwitchImageBuildDate es la fecha de construcción de la imagen, no la de instalación. |
| id, relaciones y tipo_activo | Generación y normalización del ETL/base de datos; tipo_activo = SWITCH. |

## Ajustes de significado pendientes

1. `fuentes_poder.consumo_w` figura como consumo nominal en el documento. Debe decidirse si representa consumo, potencia suministrada instantánea o capacidad máxima: son magnitudes diferentes.
2. `puerto_switch.estado` admite Encendido/Apagado/Degradado/Baja, pero la descripción habla de up/down/libre. Separar conceptualmente enlace y disponibilidad: un puerto down puede estar reservado o conectado a un equipo apagado.
3. No reutilizar los valores numéricos de los enums HPE para Aruba. Normalizar cada objeto según su definición.
4. La ausencia de información física de CPU/RAM debe mostrarse como sin datos, sin crear componentes ficticios para satisfacer los campos obligatorios de estado.

## Qué falta para construir el agente

- Elegir modelo/SKU concreto y configuración física: puertos, velocidades, fuentes, ventiladores y, si aplica, apilamiento.
- Resolver y validar OID, tipos, índices y dependencias de los MIB que se usarán.
- Definir reglas de conteo de puertos, selección de sensores y estados del ETL.
- Documentar campos manuales o sin fuente y preparar datos simulados únicamente para objetos reales.
- Para fidelidad a hardware concreto, contrastar con una captura SNMP del mismo modelo y versión. El paquete de MIB por sí solo no acredita soporte efectivo de todos los objetos.

No es necesario inventar OID para cubrir la parte principal de la ficha; el inventario detallado de CPU/RAM queda como brecha explícita.
