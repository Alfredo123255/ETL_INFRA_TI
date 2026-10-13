# Huawei OceanStor Dorado 5000 V6, instancia 02

Storage SNMPv3 simulado, serie `HWDORADO5000V6002`, con controladoras, discos,
fuentes y ventiladores propios. Los sensores de consumo y RPM son datos de
laboratorio publicados en ENTITY-SENSOR-MIB, no mediciones de un equipo real.
IP y puerto: `127.0.0.47:17700`. Usuario: `monitor_hwdorado_02`.
Clave de autenticación y privacidad: `HwDoradoLab2026Auth02` (SHA/AES).
Archivo de datos: [public.snmprec](public.snmprec).
Se inicia con `data/start_agents.bat` y se detiene con `data/stop_agents.bat`.
No crea registros en la base de datos por sí solo.
