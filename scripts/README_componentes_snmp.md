# Retirar y restaurar componentes simulados

Ejecuta los comandos desde `C:\INGESOFT\ETL_INFRA_TI` en PowerShell. Se edita solamente `data/<equipo>/public.snmprec`. No se accede a PostgreSQL ni se fuerza una iteración del ETL.

## 1. Ver equipos y componentes

```powershell
.\scripts\componentes_snmp.ps1 -Accion equipos
.\scripts\componentes_snmp.ps1 -Accion listar -Equipo hpe-dl380-01
```

La lista muestra el número de selección, índice SNMP, modelo y serie cuando existen. El número empieza en 1 **dentro de cada tipo**; no es el ID de la base de datos. Vuelve a listar después de cada retiro, porque los números disponibles pueden cambiar.

## 2. Retirar una o varias piezas

```powershell
# Ver qué se retiraría sin cambiar la captura.
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo disco -Numero 1 -VistaPrevia

# Retirar un disco con el agente encendido, sin reiniciarlo.
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo disco -Numero 1

# Otros ejemplos: ejecuta únicamente los retiros que quieras probar.
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo ram -Numero 1,2
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo cpu -Numero 1
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo fuente_poder -Numero 1
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo huawei-2288h-v5-01 -Tipo ventilador -Numero 1
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo huawei-2288h-v5-01 -Tipo tarjeta_red -Numero 1
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo controladora_raid -Numero 1
```

Tipos: `cpu`, `ram`, `disco`, `fuente_poder`, `ventilador`, `tarjeta_red`, `controladora_raid`. Alias: `psu`/`fuente`, `fan`, `nic`, `raid`, `memoria`. Puedes usar `-Todos` en lugar de `-Numero` para retirar todas las piezas de ese tipo, si el perfil sigue siendo válido.

Se soportan las capturas existentes de servidores rackeables y blade HPE/Huawei, storage HPE/Dorado, chasis HPE/E9000 y switches Aruba. Solo se listan piezas que el perfil realmente incorpora; por ejemplo, los blades no tienen fuentes ni ventiladores propios en estos perfiles. No se eliminan slots ni puertos estructurales del switch.

El script retira las filas completas de la pieza y sus dependencias conocidas (caché, volúmenes RAID, puertos de una NIC y sensores de RPM del ventilador). En Dorado CPU y RAM comparten una tabla: al retirar una CPU o una RAM se elimina únicamente su columna. Si retiras una controladora Dorado, también se retiran la CPU y la RAM que pertenecen a esa controladora; el resultado y la vista previa muestran los componentes afectados. Conserva los OID generales de identidad, temperatura y consumo; no regenera el agente ni recalcula las métricas simuladas.

Antes de guardar se comprueba la captura con el normalizador real del ETL. Si el resultado sería rechazado, se cancela sin tocar el archivo. **Los perfiles actuales de storage exigen al menos un disco y una controladora**; tampoco admiten una capacidad usada superior a la capacidad restante. No retires la última pieza obligatoria para una prueba de reconciliación: eso produciría una extracción inválida.

## 3. Restaurar

```powershell
.\scripts\componentes_snmp.ps1 -Accion restaurar -Equipo hpe-dl380-01
```

Cada ejecución restaura **el último retiro pendiente de ese equipo**. Si retiraste disco, RAM y CPU en tres operaciones, ejecuta restaurar tres veces. Se devuelve el archivo original byte a byte, incluidos los contadores y sensores que tenía al crear el respaldo. Si alguien hizo cambios ajenos al script después del retiro, la restauración se detiene para no sobrescribirlos.

Los respaldos locales están en `data/.respaldos_componentes/<equipo>/` y están excluidos de Git. No contienen ni requieren credenciales de conexión del script. No borres esa carpeta mientras quieras deshacer retiros.

## 4. Comprobar el efecto en el sistema

1. El activo debe tener el monitoreo habilitado, sin mantenimiento ni Baja, y su agente debe responder.
2. Mantén el agente encendido: snmpsim detecta la modificación y recarga su índice en la siguiente consulta. El script no detiene ni inicia procesos.
3. Espera la frecuencia configurada para ese activo. Si queda toda una categoría vacía, el ETL normalmente espera dos lecturas vacías consecutivas (`LECTURAS_VACIAS_PARA_BAJA`, valor por defecto 2).
4. Revisa la ficha y el historial: el retiro debe aparecer como `presencia = Retirado`; un componente no toma estado Baja.
5. Restaura y espera otra lectura para que el ETL detecte de nuevo las piezas. La restauración del archivo no revierte ni borra eventos históricos.

El archivo se valida y respalda antes de escribir. Se modifica su contenido conservando el mismo archivo, se ajusta su longitud y se actualiza su fecha de modificación. Esto evita el bloqueo de Windows que ocurría al intentar reemplazarlo por otro archivo y permite la recarga automática de snmpsim, incluso al retirar filas completas.

Ya no se utiliza el parámetro `-Reiniciar`. No necesitas cerrar el agente ni proporcionar credenciales al script. Si el agente estaba apagado, tendrás que iniciarlo normalmente para consultar la captura modificada.

La escritura sobre el mismo archivo no coordina las consultas SNMP que ya estén en curso. Realiza el cambio antes del siguiente ciclo ETL y evita editar la captura simultáneamente desde otro programa. Si ocurre un error de escritura, el script intenta recuperar el contenido anterior y conserva el respaldo.

También puedes usar directamente el núcleo Python (mismas acciones, sin reiniciar):

```powershell
.\.venv\Scripts\python.exe -B .\scripts\componentes_snmp.py listar --equipo huawei-dorado-01
.\.venv\Scripts\python.exe -B .\scripts\componentes_snmp.py retirar --equipo huawei-dorado-01 --tipo fuente_poder --numero 1
.\.venv\Scripts\python.exe -B .\scripts\componentes_snmp.py restaurar --equipo huawei-dorado-01
```
