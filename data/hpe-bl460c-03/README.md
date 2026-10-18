# Agente simulado: hpe-bl460c-03

Servidor HPE ProLiant BL460c Gen10 en el slot 3 del chasis
[`hpe-c7000-01`](../hpe-c7000-01/). El chasis y este agente informan el mismo
hostname y número de serie (`SN003BLD`), para que la asociación se haga por
los datos SNMP al registrar el activo.

El blade reporta estado **Degradado** y su segundo disco también está
degradado. Así se puede probar la actualización de estado y el historial de
eventos. Su IP de sistema operativo simulada es `10.10.12.15`; la IP de
gestión SNMP es `127.0.0.16:16900`. Los ventiladores, fuentes y conexiones
de red se exponen desde el agente del chasis.

## Iniciar y detener

Desde la raíz del proyecto, `data\start_agents.bat` inicia este blade junto
con los demás agentes. `data\stop_agents.bat` los detiene.

Para iniciarlo individualmente:

```bat
.\.venv\Scripts\python.exe -B data\run_responder.py --v3-engine-id=8000000001424c433033 --v3-user=HPE --v3-auth-key=Enterprise --v3-auth-proto=SHA --v3-priv-key=Enterprise --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.16:16900 --data-dir=data\hpe-bl460c-03 --cache-dir=logs\snmpsim-cache
```

El formulario de registro necesita IP y puerto, usuario SNMPv3 y clave de
autenticación. La clave de privacidad se utiliza internamente para la prueba
SNMPv3. Los OID y valores editables están en [`public.snmprec`](./public.snmprec).
