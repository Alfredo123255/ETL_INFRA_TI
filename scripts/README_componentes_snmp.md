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

# Retirar un disco y reiniciar solamente su agente.
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo disco -Numero 1 -Reiniciar

# Otros ejemplos: ejecuta únicamente los retiros que quieras probar.
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo ram -Numero 1,2 -Reiniciar
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo cpu -Numero 1 -Reiniciar
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo fuente_poder -Numero 1 -Reiniciar
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo huawei-2288h-v5-01 -Tipo ventilador -Numero 1 -Reiniciar
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo huawei-2288h-v5-01 -Tipo tarjeta_red -Numero 1 -Reiniciar
.\scripts\componentes_snmp.ps1 -Accion retirar -Equipo hpe-dl380-01 -Tipo controladora_raid -Numero 1 -Reiniciar
```

Tipos: `cpu`, `ram`, `disco`, `fuente_poder`, `ventilador`, `tarjeta_red`, `controladora_raid`. Alias: `psu`/`fuente`, `fan`, `nic`, `raid`, `memoria`. Puedes usar `-Todos` en lugar de `-Numero` para retirar todas las piezas de ese tipo, si el perfil sigue siendo válido.

Se soportan las capturas existentes de servidores rackeables y blade HPE/Huawei, storage HPE/Dorado, chasis HPE/E9000 y switches Aruba. Solo se listan piezas que el perfil realmente incorpora; por ejemplo, los blades no tienen fuentes ni ventiladores propios en estos perfiles. No se eliminan slots ni puertos estructurales del switch.

El script retira las filas completas de la pieza y sus dependencias conocidas (caché, volúmenes RAID, puertos de una NIC y sensores de RPM del ventilador). En Dorado CPU y RAM comparten una tabla: al retirar una CPU o una RAM se elimina únicamente su columna. Si retiras una controladora Dorado, también se retiran la CPU y la RAM que pertenecen a esa controladora; el resultado y la vista previa muestran los componentes afectados. Conserva los OID generales de identidad, temperatura y consumo; no regenera el agente ni recalcula las métricas simuladas.

Antes de guardar se comprueba la captura con el normalizador real del ETL. Si el resultado sería rechazado, se cancela sin tocar el archivo. **Los perfiles actuales de storage exigen al menos un disco y una controladora**; tampoco admiten una capacidad usada superior a la capacidad restante. No retires la última pieza obligatoria para una prueba de reconciliación: eso produciría una extracción inválida.

## 3. Restaurar

```powershell
.\scripts\componentes_snmp.ps1 -Accion restaurar -Equipo hpe-dl380-01 -Reiniciar
```

Cada ejecución restaura **el último retiro pendiente de ese equipo**. Si retiraste disco, RAM y CPU en tres operaciones, ejecuta restaurar tres veces. Se devuelve el archivo original byte a byte, incluidos los contadores y sensores que tenía al crear el respaldo. Si alguien hizo cambios ajenos al script después del retiro, la restauración se detiene para no sobrescribirlos.

Los respaldos locales están en `data/.respaldos_componentes/<equipo>/` y están excluidos de Git. No contienen ni requieren credenciales de conexión del script. No borres esa carpeta mientras quieras deshacer retiros.

## 4. Comprobar el efecto en el sistema

1. El activo debe tener el monitoreo habilitado, sin mantenimiento ni Baja, y su agente debe responder.
2. Usa `-Reiniciar` o reinicia manualmente **solo el agente modificado**. El script no detiene FastAPI, Java, el frontend ni el programador ETL.
3. Espera la frecuencia configurada para ese activo. Si queda toda una categoría vacía, el ETL normalmente espera dos lecturas vacías consecutivas (`LECTURAS_VACIAS_PARA_BAJA`, valor por defecto 2).
4. Revisa la ficha y el historial: el retiro debe aparecer como `presencia = Retirado`; un componente no toma estado Baja.
5. Restaura y espera otra lectura para que el ETL detecte de nuevo las piezas. La restauración del archivo no revierte ni borra eventos históricos.

En Windows snmpsim puede mantener la captura abierta e impedir reemplazarla. Con `-Reiniciar`, el lanzador valida primero el cambio, detiene solo el agente seleccionado, guarda y lo inicia nuevamente en segundo plano. También intenta reabrirlo si la escritura falla. Reutiliza su comando en memoria, sin copiar claves a archivos. Los registros quedan en `logs/componentes_snmp/`.

Sin `-Reiniciar`, detén manualmente ese agente antes de modificar su captura y vuelve a iniciarlo después. Si pediste reiniciar pero el agente estaba apagado, el script lo avisa y guarda el archivo; no inventa credenciales para iniciarlo. Mientras el agente reinicia, una consulta puede fallar transitoriamente: realiza la prueba cuando no haya una extracción en curso para evitar confundir ese reinicio con el retiro del componente.

También puedes usar directamente el núcleo Python (mismas acciones, sin reinicio automático):

```powershell
.\.venv\Scripts\python.exe -B .\scripts\componentes_snmp.py listar --equipo huawei-dorado-01
.\.venv\Scripts\python.exe -B .\scripts\componentes_snmp.py retirar --equipo huawei-dorado-01 --tipo fuente_poder --numero 1
.\.venv\Scripts\python.exe -B .\scripts\componentes_snmp.py restaurar --equipo huawei-dorado-01
```
