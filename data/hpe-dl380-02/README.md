# Agente simulado: hpe-dl380-02

HPE ProLiant DL380 Gen10, creado a partir de `hpe-dl380-01` con todos sus OID.
Conserva el inventario y estados del original. Identidad, series de componentes,
MAC e IP del SO son propias del nuevo equipo. No se registra automáticamente en BD.

| Dato | Valor |
|---|---|
| IP de gestión y puerto | `127.0.0.17:17800` |
| Usuario | `HPE` |
| Clave de autenticación y privacidad | `Enterprise` |
| Contexto | `public` |
| Hostname | `hpe-dl380-02` |
| Serie del equipo | `CZ38020ABC` |
| IP del SO | `10.10.12.17` |

## Inicio individual desde la raíz del ETL

```powershell
python data/run_responder.py --v3-engine-id=8000000001444c3338303032 --v3-user=HPE --v3-auth-key='Enterprise' --v3-auth-proto=SHA --v3-priv-key='Enterprise' --v3-priv-proto=AES --agent-udpv4-endpoint=127.0.0.17:17800 --data-dir="C:\INGESOFT\ETL_INFRA_TI\data\hpe-dl380-02" --cache-dir="C:\INGESOFT\ETL_INFRA_TI\logs\snmpsim-cache-dl380-02"
```

El agente también está incluido en `data/start_agents.bat`, `data/stop_agents.bat`
y en el manifiesto usado por `data/servicio_agentes.py`.
Las métricas aplicables son MT-01, 02, 03, 04, 05, 06, 09 y 12.
