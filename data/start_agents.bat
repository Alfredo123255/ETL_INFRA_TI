@echo off
REM Levanta los dos agentes SNMP simulados (hpe-dl380-01 y hpe-dl360-01),
REM cada uno en su propia ventana cmd independiente, para que corran en
REM paralelo y se vea el log en vivo de cada uno.
REM
REM Cerrar la ventana (o Ctrl+C dentro de ella) detiene ese agente. Si el
REM proceso termina o falla, la ventana queda abierta con "Presione una
REM tecla..." para poder leer el error antes de que se cierre.
REM
REM Credenciales y puertos documentados en data\hpe-dl380-01\README.md
REM y data\hpe-dl360-01\README.md.

setlocal

REM Raiz del repo = carpeta padre de esta carpeta (data\)
set "REPO_ROOT=%~dp0.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

echo Repo: %REPO_ROOT%
echo.

echo Iniciando hpe-dl380-01 en 127.0.0.1:16100 ...
start "hpe-dl380-01 (127.0.0.1:16100)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001444c333830 --v3-user=monitor_dl380 --v3-auth-key=Kr7aY5nT2LdUco2B5IAZ --v3-auth-proto=SHA --v3-priv-key=GpoJkRAhPOZg3vA4qHyT --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.1:16100 --data-dir="%REPO_ROOT%\data\hpe-dl380-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-dl380-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

REM Pequena pausa para que no compitan por el mismo archivo de cache al arrancar
timeout /t 2 /nobreak >nul

echo Iniciando hpe-dl360-01 en 127.0.0.1:16200 ...
start "hpe-dl360-01 (127.0.0.1:16200)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001444c333630 --v3-user=monitor_dl360 --v3-auth-key=3nRFCWnSuDougjTVD3SV --v3-auth-proto=SHA --v3-priv-key=Wru30SG1uouCjtcd5h7P --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.1:16200 --data-dir="%REPO_ROOT%\data\hpe-dl360-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-dl360-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

echo.
echo Listo. Se abrieron 2 ventanas, una por agente.
echo Para verificar: python "%REPO_ROOT%\data\verify_agents.py"

endlocal
