@echo off
REM Inicia todos los agentes SNMP simulados en ventanas independientes.
REM Cerrar una ventana o pulsar Ctrl+C detiene ese agente.
REM Para detenerlos todos, ejecutar data\stop_agents.bat.
setlocal
set "REPO_ROOT=%~dp0.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
REM Los agentes usan snmpsim instalado en el Python base de Miniconda.
REM Anteponerlo evita que un .venv activado invoque otro Python sin snmpsim.
set "PATH=%USERPROFILE%\miniconda3;%PATH%"
python -B -c "import snmpsim, pysnmp" >nul 2>&1
if errorlevel 1 (
  echo Error: el Python de Miniconda no encuentra snmpsim o pysnmp.
  echo Instale las dependencias de requirements.txt en ese Python.
  exit /b 1
)
echo Repo: %REPO_ROOT%
echo.
echo Iniciando hpe-dl380-01 en 127.0.0.11:16100 ...
start "hpe-dl380-01 (127.0.0.11:16100)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001444c333830 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.11:16100 --data-dir="%REPO_ROOT%\data\hpe-dl380-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-dl380-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-dl360-01 en 127.0.0.12:16200 ...
start "hpe-dl360-01 (127.0.0.12:16200)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001444c333630 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.12:16200 --data-dir="%REPO_ROOT%\data\hpe-dl360-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-dl360-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-c7000-01 en 127.0.0.15:16300 ...
start "hpe-c7000-01 (127.0.0.15:16300)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000014337303030 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.15:16300 --data-dir="%REPO_ROOT%\data\hpe-c7000-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-c7000-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-bl460c-01 en 127.0.0.13:16400 ...
start "hpe-bl460c-01 (127.0.0.13:16400)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001424c433031 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.13:16400 --data-dir="%REPO_ROOT%\data\hpe-bl460c-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-bl460c-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-bl460c-02 en 127.0.0.14:16500 ...
start "hpe-bl460c-02 (127.0.0.14:16500)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001424c433032 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.14:16500 --data-dir="%REPO_ROOT%\data\hpe-bl460c-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-bl460c-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-bl460c-03 en 127.0.0.16:16900 ...
start "hpe-bl460c-03 (127.0.0.16:16900)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001424c433033 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.16:16900 --data-dir="%REPO_ROOT%\data\hpe-bl460c-03" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-bl460c-03 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando aruba-cx-sw01 en 127.0.0.20:16600 ...
start "aruba-cx-sw01 (127.0.0.20:16600)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000153573031 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.20:16600 --data-dir="%REPO_ROOT%\data\aruba-cx-sw01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [aruba-cx-sw01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-storage-fc-01 en 127.0.0.30:16700 ...
start "hpe-storage-fc-01 (127.0.0.30:16700)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000153543031 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.30:16700 --data-dir="%REPO_ROOT%\data\hpe-storage-fc-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-storage-fc-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-storage-fc-02 en 127.0.0.31:16800 ...
start "hpe-storage-fc-02 (127.0.0.31:16800)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000153543032 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.31:16800 --data-dir="%REPO_ROOT%\data\hpe-storage-fc-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-storage-fc-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-2288h-v5-01 en 127.0.0.40:17000 ...
start "huawei-2288h-v5-01 (127.0.0.40:17000)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001485732323838 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.40:17000 --data-dir="%REPO_ROOT%\data\huawei-2288h-v5-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-2288h-v5-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-ch121-v5-01 en 127.0.0.41:17100 ...
start "huawei-ch121-v5-01 (127.0.0.41:17100)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000148574348313231 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.41:17100 --data-dir="%REPO_ROOT%\data\huawei-ch121-v5-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-ch121-v5-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-e9000-01 en 127.0.0.42:17200 ...
start "huawei-e9000-01 (127.0.0.42:17200)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000148574539303030 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.42:17200 --data-dir="%REPO_ROOT%\data\huawei-e9000-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-e9000-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-dorado-01 en 127.0.0.43:17300 ...
start "huawei-dorado-01 (127.0.0.43:17300)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000014857444f5241444f --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.43:17300 --data-dir="%REPO_ROOT%\data\huawei-dorado-01" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-dorado-01 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-2288h-v5-02 en 127.0.0.44:17400 ...
start "huawei-2288h-v5-02 (127.0.0.44:17400)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000014857323238383032 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.44:17400 --data-dir="%REPO_ROOT%\data\huawei-2288h-v5-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-2288h-v5-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-ch121-v5-02 en 127.0.0.45:17500 ...
start "huawei-ch121-v5-02 (127.0.0.45:17500)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001485743483132313032 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.45:17500 --data-dir="%REPO_ROOT%\data\huawei-ch121-v5-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-ch121-v5-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-e9000-02 en 127.0.0.46:17600 ...
start "huawei-e9000-02 (127.0.0.46:17600)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001485745393030303032 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.46:17600 --data-dir="%REPO_ROOT%\data\huawei-e9000-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-e9000-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-dorado-02 en 127.0.0.47:17700 ...
start "huawei-dorado-02 (127.0.0.47:17700)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000014857444f5241444f3032 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.47:17700 --data-dir="%REPO_ROOT%\data\huawei-dorado-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-dorado-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

echo Iniciando hpe-dl380-02 en 127.0.0.17:17800 ...
start "hpe-dl380-02 (127.0.0.17:17800)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=8000000001444c3338303032 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.17:17800 --data-dir="%REPO_ROOT%\data\hpe-dl380-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-dl380-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"

echo Iniciando aruba-cx-sw02 en 127.0.0.21:17900 ...
start "aruba-cx-sw02 (127.0.0.21:17900)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000161727562612d63782d73773032 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.21:17900 --data-dir="%REPO_ROOT%\data\aruba-cx-sw02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [aruba-cx-sw02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando aruba-cx-sw03 en 127.0.0.22:18000 ...
start "aruba-cx-sw03 (127.0.0.22:18000)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000161727562612d63782d73773033 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.22:18000 --data-dir="%REPO_ROOT%\data\aruba-cx-sw03" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [aruba-cx-sw03 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando aruba-cx-sw04 en 127.0.0.23:18100 ...
start "aruba-cx-sw04 (127.0.0.23:18100)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000161727562612d63782d73773034 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.23:18100 --data-dir="%REPO_ROOT%\data\aruba-cx-sw04" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [aruba-cx-sw04 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando aruba-cx-sw05 en 127.0.0.24:18200 ...
start "aruba-cx-sw05 (127.0.0.24:18200)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=800000000161727562612d63782d73773035 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.24:18200 --data-dir="%REPO_ROOT%\data\aruba-cx-sw05" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [aruba-cx-sw05 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-c7000-02 en 127.0.0.18:18300 ...
start "hpe-c7000-02 (127.0.0.18:18300)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000016870652d63373030302d3032 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.18:18300 --data-dir="%REPO_ROOT%\data\hpe-c7000-02" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-c7000-02 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-bl460c-04 en 127.0.0.19:18400 ...
start "hpe-bl460c-04 (127.0.0.19:18400)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000016870652d626c343630632d3034 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.19:18400 --data-dir="%REPO_ROOT%\data\hpe-bl460c-04" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-bl460c-04 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando hpe-bl460c-05 en 127.0.0.25:18500 ...
start "hpe-bl460c-05 (127.0.0.25:18500)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000016870652d626c343630632d3035 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.25:18500 --data-dir="%REPO_ROOT%\data\hpe-bl460c-05" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [hpe-bl460c-05 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-e9000-03 en 127.0.0.48:18600 ...
start "huawei-e9000-03 (127.0.0.48:18600)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000016875617765692d65393030302d3033 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.48:18600 --data-dir="%REPO_ROOT%\data\huawei-e9000-03" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-e9000-03 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-ch121-v5-03 en 127.0.0.49:18700 ...
start "huawei-ch121-v5-03 (127.0.0.49:18700)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000016875617765692d63683132312d76352d3033 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.49:18700 --data-dir="%REPO_ROOT%\data\huawei-ch121-v5-03" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-ch121-v5-03 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

echo Iniciando huawei-ch121-v5-04 en 127.0.0.50:18800 ...
start "huawei-ch121-v5-04 (127.0.0.50:18800)" cmd /c "python "%REPO_ROOT%\data\run_responder.py" --v3-engine-id=80000000016875617765692d63683132312d76352d3034 --v3-user=Administrator --v3-auth-key=Admin@9000 --v3-auth-proto=SHA --v3-priv-key=Admin@9000 --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.50:18800 --data-dir="%REPO_ROOT%\data\huawei-ch121-v5-04" --cache-dir="%REPO_ROOT%\logs\snmpsim-cache" & echo. & echo [huawei-ch121-v5-04 termino. Presione una tecla para cerrar esta ventana] & pause >nul"
timeout /t 2 /nobreak >nul

endlocal
