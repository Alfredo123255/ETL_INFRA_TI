@echo off
REM Levanta los agentes SNMP simulados de los servidores (hpe-dl380-01,
REM hpe-dl360-01, hpe-bl460c-01, hpe-bl460c-02), del switch (aruba-cx-sw01)
REM y de las unidades de storage Fibre Channel (hpe-storage-fc-01,
REM hpe-storage-fc-02), cada uno en su propia ventana cmd independiente,
REM para que corran en paralelo y se vea el log en vivo de cada uno.
REM hpe-c7000-01 (chasis) no se incluye en este script; levantarlo a mano
REM con los parametros de data\hpe-c7000-01\README.md.
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

echo Iniciando hpe-dl380-01 en 127.0.0.11:16100 ...
start "hpe-dl380-01 (127.0.0.11:16100)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001444c333830 --v3-user=monitor_dl380 --v3-auth-key=Kr7aY5nT2LdUco2B5IAZ --v3-auth-proto=SHA --v3-priv-key=GpoJkRAhPOZg3vA4qHyT --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.11:16100 --data-dir="%REPO_ROOT%\data\hpe-dl380-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-dl380-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

REM Pequena pausa para que no compitan por el mismo archivo de cache al arrancar
timeout /t 2 /nobreak >nul

echo Iniciando hpe-dl360-01 en 127.0.0.12:16200 ...
start "hpe-dl360-01 (127.0.0.12:16200)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001444c333630 --v3-user=monitor_dl360 --v3-auth-key=3nRFCWnSuDougjTVD3SV --v3-auth-proto=SHA --v3-priv-key=Wru30SG1uouCjtcd5h7P --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.12:16200 --data-dir="%REPO_ROOT%\data\hpe-dl360-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-dl360-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

REM Pequena pausa para que no compitan por el mismo archivo de cache al arrancar
timeout /t 2 /nobreak >nul

echo Iniciando hpe-bl460c-01 en 127.0.0.13:16400 ...
start "hpe-bl460c-01 (127.0.0.13:16400)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001424c433031 --v3-user=monitor_bl460c01 --v3-auth-key=Yb2QzP9mLxT4wVh8Kd3R --v3-auth-proto=SHA --v3-priv-key=Ft6NcE1oRgJ5sWp2Ux9M --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.13:16400 --data-dir="%REPO_ROOT%\data\hpe-bl460c-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-bl460c-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

REM Pequena pausa para que no compitan por el mismo archivo de cache al arrancar
timeout /t 2 /nobreak >nul

echo Iniciando hpe-bl460c-02 en 127.0.0.14:16500 ...
start "hpe-bl460c-02 (127.0.0.14:16500)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001424c433032 --v3-user=monitor_bl460c02 --v3-auth-key=Ht4RxQ8kMbZ3vNp6Ld1J --v3-auth-proto=SHA --v3-priv-key=Sc9WjE2yTfL7uKq4Gz5V --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.14:16500 --data-dir="%REPO_ROOT%\data\hpe-bl460c-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-bl460c-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

REM Pequena pausa para que no compitan por el mismo archivo de cache al arrancar
timeout /t 2 /nobreak >nul

echo Iniciando aruba-cx-sw01 en 127.0.0.20:16600 ...
start "aruba-cx-sw01 (127.0.0.20:16600)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000153573031 --v3-user=monitor_sw01 --v3-auth-key=2JePukZ17WBQg10i3J3U --v3-auth-proto=SHA --v3-priv-key=ZynkEa6RTaPcFsqG1Oc5 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.20:16600 --data-dir="%REPO_ROOT%\data\aruba-cx-sw01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [aruba-cx-sw01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

REM Pequena pausa para que no compitan por el mismo archivo de cache al arrancar
timeout /t 2 /nobreak >nul

echo Iniciando hpe-storage-fc-01 en 127.0.0.30:16700 ...
start "hpe-storage-fc-01 (127.0.0.30:16700)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000153543031 --v3-user=monitor_storagefc01 --v3-auth-key=RcVQ87sKGKNAXteaPhvF --v3-auth-proto=SHA --v3-priv-key=87KIBACIxZCukpKjai0Z --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.30:16700 --data-dir="%REPO_ROOT%\data\hpe-storage-fc-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-storage-fc-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

REM Pequena pausa para que no compitan por el mismo archivo de cache al arrancar
timeout /t 2 /nobreak >nul

echo Iniciando hpe-storage-fc-02 en 127.0.0.31:16800 ...
start "hpe-storage-fc-02 (127.0.0.31:16800)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000153543032 --v3-user=monitor_storagefc02 --v3-auth-key=SMkMLpmciBdaLR9pfDux --v3-auth-proto=SHA --v3-priv-key=2VcFacU3YHQ1CqwgAg7D --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.31:16800 --data-dir="%REPO_ROOT%\data\hpe-storage-fc-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-storage-fc-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

echo.
echo Listo. Se abrieron 7 ventanas, una por agente (hpe-dl380-01, hpe-dl360-01,
echo hpe-bl460c-01, hpe-bl460c-02, aruba-cx-sw01, hpe-storage-fc-01,
echo hpe-storage-fc-02). hpe-c7000-01 no se levanta desde este script.
echo Para verificar: python "%REPO_ROOT%\data\verify_agents.py"

endlocal
