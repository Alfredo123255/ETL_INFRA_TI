"""Comprueba los 12 MT aplicables mediante SNMP, sin escribir en PostgreSQL.

Uso: python -B data/validar_metricas.py --salida RUTA
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pydantic import SecretStr
from etl.config import cargar_configuracion
from etl.ciclo import preparar_registro_activo
from etl.snmp_cliente import ConexionSNMP
from etl.metricas import construir_metricas, NOMBRES_METRICAS

RED={"red_trafico_entrada_mbps","red_trafico_salida_mbps","red_ancho_banda_mbps","red_utilizacion_pct"}
EQUIPO={"equipo_temperatura_c","equipo_consumo_w"}
CPU_RAM={"cpu_uso_ghz","ram_uso_gb"}
STORAGE={"almacenamiento_uso_tb","almacenamiento_iops","almacenamiento_latencia_ms",
    "almacenamiento_throughput_lectura_mbps","almacenamiento_throughput_escritura_mbps"}
ESPERADAS={"SERVIDOR":EQUIPO|CPU_RAM|RED|{"disco_uso_gb"},
           "SWITCH":EQUIPO|CPU_RAM|RED,"CHASIS":EQUIPO|RED,"STORAGE":EQUIPO|RED|STORAGE}
MT={"MT-01":{"cpu_uso_ghz"},"MT-02":{"ram_uso_gb"},"MT-03":{"disco_uso_gb"},
    "MT-04":{"equipo_temperatura_c"},"MT-05":{"equipo_consumo_w"},
    "MT-06":{"red_trafico_entrada_mbps","red_trafico_salida_mbps"},
    "MT-07":{"almacenamiento_uso_tb"},"MT-08":{"almacenamiento_iops"},
    "MT-09":{"red_ancho_banda_mbps"},"MT-10":{"almacenamiento_latencia_ms"},
    "MT-11":{"almacenamiento_throughput_lectura_mbps","almacenamiento_throughput_escritura_mbps"},
    "MT-12":{"red_utilizacion_pct"}}


async def validar(config):
    agentes=json.loads((ROOT/"data/agentes-docker.json").read_text())
    semaforo=asyncio.Semaphore(3)
    async def uno(a):
        async with semaforo:
            try:
                c=ConexionSNMP(a["host"],a["puerto"],a["usuario"],SecretStr(a["auth_key"]),
                    config.snmp_context_name,config.snmp_timeout,config.snmp_retries)
                ficha=await preparar_registro_activo(c,config)
                activo=ficha["activo"]
                fecha=datetime.now(timezone.utc).replace(tzinfo=None)
                metricas=construir_metricas(activo["tipo_activo"],ficha,fecha)
                nombres={m["nombre_metrica"] for m in metricas}
                faltantes=ESPERADAS[activo["tipo_activo"]]-nombres
                assert not faltantes, "Faltan: "+", ".join(sorted(faltantes))
                assert nombres<=NOMBRES_METRICAS
                assert all(m["valor"].is_finite() and m["valor"]>=0 for m in metricas)
                assert all(m["valor"]<=100 for m in metricas if m["nombre_metrica"]=="red_utilizacion_pct")
                assert all(m.get("componente_tipo") and m.get("componente_serial")
                    for m in metricas if m["nombre_metrica"].startswith("red_"))
                resultado={"agente":a["nombre"],"tipo":activo["tipo_activo"],
                    "marca":activo["fabricante"],"ok":True,"cantidad":len(metricas),
                    "mt_verificados":[mt for mt,ns in MT.items() if ns<=nombres],
                    "metricas":[{k:str(v) if isinstance(v,(Decimal,datetime)) else v for k,v in m.items()} for m in metricas]}
            except Exception as e:
                # Nunca imprimir excepciones de transporte que puedan incluir credenciales.
                resultado={"agente":a["nombre"],"ok":False,"error_tipo":type(e).__name__}
                if isinstance(e,AssertionError):resultado["detalle"]=str(e)
            print(json.dumps({k:v for k,v in resultado.items() if k!="metricas"},ensure_ascii=True),flush=True)
            return resultado
    return await asyncio.gather(*(uno(a) for a in agentes))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--salida",type=Path,required=True)
    args=p.parse_args();args.salida.mkdir(parents=True,exist_ok=True)
    resultados=asyncio.run(validar(cargar_configuracion()))
    nombres={m["nombre_metrica"] for r in resultados for m in r.get("metricas",[])}
    ok=all(r["ok"] for r in resultados) and nombres==NOMBRES_METRICAS
    evidencia={"ok":ok,"agentes":len(resultados),"correctos":sum(r["ok"] for r in resultados),
        "nombres_verificados":sorted(nombres),"resultados":resultados}
    (args.salida/"lecturas_snmp.json").write_text(json.dumps(evidencia,ensure_ascii=False,indent=2),encoding="utf-8")
    lineas=["# Validación de los 12 MT", "", "Consultas SNMP reales a los agentes simulados; sin escrituras en BD.", "",
        "| Agente | Tipo | MT verificados | Resultado |", "|---|---|---|---|"]
    for r in resultados:
        lineas.append(f"| {r['agente']} | {r.get('tipo','—')} | {', '.join(r.get('mt_verificados',[]))} | {'Correcto' if r['ok'] else r.get('detalle',r.get('error_tipo'))} |")
    lineas.extend(["",f"Resultado: {sum(r['ok'] for r in resultados)}/{len(resultados)} agentes; {len(nombres)}/14 nombres del catálogo.",
        "", "Las métricas se exigen según el tipo de activo. No se exige CPU/RAM/discos a un chasis ni IOPS a un servidor.",
        "La simulación de HPE storage conserva el MIB Nimble prestado. Huawei usa HOST-RESOURCES-MIB para volúmenes del SO en el agente de laboratorio."])
    (args.salida/"RESULTADOS_MT.md").write_text("\n".join(lineas)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in evidencia.items() if k!="resultados"}),flush=True)
    return 0 if ok else 1


if __name__=="__main__":raise SystemExit(main())
