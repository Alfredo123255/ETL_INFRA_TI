@echo off
REM Levanta los agentes SNMP simulados de los servidores (hpe-dl380-01,
REM hpe-dl360-01, hpe-bl460c-01, hpe-bl460c-02), cada uno en su propia
REM ventana cmd independiente, para que corran en paralelo y se vea el log
REM en vivo de cada uno. hpe-c7000-01 (chasis) no se incluye en este script;
REM levantarlo a mano con los parametros de data\hpe-c7000-01\README.md.
REM
REM Cerrar la ventana (o Ctrl+C dentro de ella) detiene ese agente. Si el
REM proceso termina o falla, la ventana queda abierta con "Presione una
REM tecla..." para poder leer el error antes de que se cierre.
REM
REM Credenciales y puertos documentados en el README.md de cada carpeta
REM data\hpe-<agente>\.

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

REM Pequena pausa para que no compitan por el mismo archivo de cache al arrancar
timeout /t 2 /nobreak >nul

echo Iniciando hpe-bl460c-01 en 127.0.0.1:16400 ...
start "hpe-bl460c-01 (127.0.0.1:16400)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001424c433031 --v3-user=monitor_bl460c01 --v3-auth-key=Yb2QzP9mLxT4wVh8Kd3R --v3-auth-proto=SHA --v3-priv-key=Ft6NcE1oRgJ5sWp2Ux9M --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.1:16400 --data-dir="%REPO_ROOT%\data\hpe-bl460c-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-bl460c-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

REM Pequena pausa para que no compitan por el mismo archivo de cache al arrancar
timeout /t 2 /nobreak >nul

echo Iniciando hpe-bl460c-02 en 127.0.0.1:16500 ...
start "hpe-bl460c-02 (127.0.0.1:16500)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001424c433032 --v3-user=monitor_bl460c02 --v3-auth-key=Ht4RxQ8kMbZ3vNp6Ld1J --v3-auth-proto=SHA --v3-priv-key=Sc9WjE2yTfL7uKq4Gz5V --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.1:16500 --data-dir="%REPO_ROOT%\data\hpe-bl460c-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-bl460c-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

echo.
echo Listo. Se abrieron 4 ventanas, una por agente (hpe-dl380-01, hpe-dl360-01,
echo hpe-bl460c-01, hpe-bl460c-02). hpe-c7000-01 no se levanta desde este script.
echo Para verificar: python "%REPO_ROOT%\data\verify_agents.py"

endlocal
