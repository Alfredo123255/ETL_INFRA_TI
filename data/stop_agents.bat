@echo off
REM Detiene los agentes SNMP simulados levantados con start_agents.bat (o a
REM mano con run_responder.py), cerrando tambien sus ventanas cmd.
REM
REM Busca los procesos cmd.exe / python.exe cuya linea de comandos contiene
REM "run_responder.py" y los termina junto con su arbol de procesos.
REM Incluye hpe-bl460c-03 y todos los demas agentes, sin depender del puerto.

setlocal

set "PS_CMD=$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*run_responder.py*' -and $_.ProcessId -ne $PID }; if (-not $p) { Write-Host 'No hay agentes en ejecucion.'; exit 0 }; $p | Sort-Object { $_.Name -ne 'cmd.exe' } | ForEach-Object { Write-Host ('Deteniendo ' + $_.Name + ' (PID ' + $_.ProcessId + ')'); taskkill /PID $_.ProcessId /T /F *> $null }; Write-Host ''; Write-Host 'Agentes detenidos.'"

powershell -NoProfile -ExecutionPolicy Bypass -Command "%PS_CMD%"

endlocal
