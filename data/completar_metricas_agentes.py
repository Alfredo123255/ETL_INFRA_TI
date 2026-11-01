"""Añade OID de métricas al laboratorio conservando identidad y estados existentes.

HPE: CPQHOST-MIB para volúmenes; Huawei: HOST-RESOURCES-MIB, extensión del
agente de laboratorio (no implica soporte de volúmenes en iBMC real).
IF-MIB usa Counter64; HPE storage conserva su bloque Nimble prestado.
"""
from pathlib import Path
import argparse
import re

DATA=Path(__file__).resolve().parent
IF="1.3.6.1.2.1.2.2.1"
IFX="1.3.6.1.2.1.31.1.1.1"
CPQ="1.3.6.1.4.1.232.18.2.3.1.1"
FS="1.3.6.1.4.1.232.11.2.4.1.1"
HR="1.3.6.1.2.1.25.2.3.1"


def valor(data, oid, defecto=0):
    if oid not in data:return defecto
    tag,value=data[oid]
    if ":numeric" in tag:
        value=dict(p.split("=",1) for p in value.split(",")).get("initial","0")
    try:return int(value)
    except ValueError:return defecto


def indices(data, base):
    return sorted({oid[len(base)+1:] for oid in data if oid.startswith(base+".")},
                  key=lambda x:tuple(map(int,x.split("."))))


def completar(nombre, data):
    def poner(oid,tag,value):data.setdefault(oid,(tag,str(value)))
    def contador(oid,tag,rate,initial):
        previo=data.get(oid)
        if previo and ":numeric" in previo[0]:return
        base=valor(data,oid,initial)
        data[oid]=(tag+":numeric",f"rate={rate},initial={base}")
    es_storage="storage-fc" in nombre or "dorado" in nombre
    es_servidor=any(x in nombre for x in ("dl360","dl380","bl460","2288h","ch121"))
    es_hpe=nombre.startswith("hpe-")
    if es_servidor:
        # Dos volúmenes cuya suma no excede la capacidad instalada simulada.
        if es_hpe:
            total_mb=sum(valor(data,f"1.3.6.1.4.1.232.3.2.3.1.1.9.{i}")
                         for i in indices(data,"1.3.6.1.4.1.232.3.2.3.1.1.9"))
            if total_mb<=0:
                total_mb=sum(valor(data,f"1.3.6.1.4.1.232.3.2.5.1.1.45.{i}")
                             for i in indices(data,"1.3.6.1.4.1.232.3.2.5.1.1.45"))
        else:
            # Huawei iBMC: driveCapacity en GB en los perfiles actuales.
            base="1.3.6.1.4.1.2011.2.235.1.1.18.50.1"
            total_mb=sum(valor(data,f"{base}.12.{i}")*1024 for i in indices(data,base+".12"))
        if total_mb<=0:total_mb=1024*1024
        volumenes=(total_mb//4,total_mb-total_mb//4)
        for i,total in enumerate(volumenes,1):
            usado=total*(55 if i==1 else 65)//100
            if es_hpe:
                for col,tag,value in ((1,"2",i),(2,"4",f"Volumen {i}"),(3,"2",total),
                                      (4,"2",usado),(5,"2",usado*100//total)):
                    poner(f"{FS}.{col}.{i}",tag,value)
            else:
                for col,tag,value in ((1,"2",i),(2,"6","1.3.6.1.2.1.25.2.1.4"),
                    (3,"4",f"Volumen {i}"),(4,"2",4096),(5,"2",total*256),(6,"2",usado*256)):
                    poner(f"{HR}.{col}.{i}",tag,value)

    # Completa las interfaces ausentes sin modificar la salud de las NIC.
    if not indices(data,IF+".3"):
        if "dorado" in nombre:
            ports=indices(data,"1.3.6.1.4.1.34774.4.1.19.8.7.1.9")
            perfiles=[(i,56,valor(data,f"1.3.6.1.4.1.34774.4.1.19.8.7.1.9.{i}")*1000,
                       1 if valor(data,f"1.3.6.1.4.1.34774.4.1.19.8.7.1.4.{i}")==1 else 2)
                      for i in ports]
        elif es_storage:
            ports=indices(data,"1.3.6.1.4.1.232.16.2.7.1.1.2") or ["1","2"]
            perfiles=[(str(n),56,16000,1) for n,_ in enumerate(ports,1)]
        else:
            ports=indices(data,CPQ+".4") or indices(data,CPQ+".39")
            perfiles=[]
            for n,i in enumerate(ports,1):
                modelo=data.get(CPQ+".39."+i,("4",""))[1]
                match=re.search(r"(\d+)\s*Gb",modelo,re.I)
                mbps=valor(data,CPQ+".36."+i,(int(match.group(1))*1000 if match else 1000))
                estado=valor(data,CPQ+".14."+i,2 if valor(data,CPQ+".12."+i,2)==2 else 4)
                poner(CPQ+".36."+i,"66",mbps)
                poner(CPQ+".33."+i,"66",mbps*1000000 if mbps<=4000 else 0)
                poner(CPQ+".14."+i,"2",estado)
                contador(CPQ+".37."+i,"65",4000000*n,100000000*n)
                contador(CPQ+".38."+i,"65",2000000*n,80000000*n)
                perfiles.append((str(n),6,mbps,1 if estado==2 else 2))
        if not perfiles and es_hpe and "bl460" in nombre:
            # Interfaces propias del blade; no duplica los puertos del chasis.
            perfiles=[("1",6,10000,1),("2",6,10000,1)]
        for i,tipo,mbps,oper in perfiles:
            for col,tag,value in ((1,"2",int(i)),(2,"4",("FC" if tipo==56 else "Ethernet")+i),
                 (3,"2",tipo),(5,"66",min(mbps*1000000,4294967295)),(7,"2",1),(8,"2",oper)):
                poner(f"{IF}.{col}.{i}",tag,value)
            for col,tag,value in ((1,"4",("FC" if tipo==56 else "Ethernet")+i),
                                  (15,"66",mbps),(19,"67",0)):
                poner(f"{IFX}.{col}.{i}",tag,value)
    for n,i in enumerate(indices(data,IF+".3"),1):
        if valor(data,IF+".3."+i) not in (6,56):continue
        velocidad=valor(data,IFX+".15."+i,valor(data,IF+".5."+i)//1000000)
        activo=valor(data,IF+".8."+i)==1
        # Menos del 1 % del enlace; positivo y acumulativo en laboratorio.
        entrada=max(1,velocidad*1000000//800) if activo else 0
        salida=entrada//2
        contador(IFX+".6."+i,"70",entrada,4100000000*n)
        contador(IFX+".10."+i,"70",salida,3200000000*n)
        poner(IFX+".19."+i,"67",0)
    if "dorado" in nombre:
        for i in indices(data,"1.3.6.1.4.1.34774.4.1.21.3.1.1"):
            base="1.3.6.1.4.1.34774.4.1.21.3.1"
            lectura,escritura=400+int(i)*20,200+int(i)*10
            poner(f"{base}.8.{i}","66",lectura+escritura)
            poner(f"{base}.9.{i}","66",lectura)
            poner(f"{base}.10.{i}","66",escritura)
    return data


def actualizar(path):
    comentarios=[];data={}
    for linea in path.read_text(encoding="ascii").splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            comentarios.append(linea);continue
        oid,tag,value=linea.split("|",2)
        data[oid]=(tag,value)
    completar(path.parent.name,data)
    # Corrige exclusivamente el error de tipeo conocido del fabricante Intel.
    fabricante="1.3.6.1.4.1.232.1.2.2.1.1.8.1"
    if path.parent.name=="hpe-bl460c-02" and data.get(fabricante)==("2","2f"):
        data[fabricante]=("2","2")
    lineas=comentarios+[f"{oid}|{tag}|{value}" for oid,(tag,value) in sorted(
        data.items(),key=lambda p:tuple(map(int,p[0].split("."))))]
    path.write_text("\n".join(lineas)+"\n",encoding="ascii")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solo",nargs="+")
    args=parser.parse_args()
    for path in DATA.glob("*/public.snmprec"):
        if args.solo and path.parent.name not in args.solo:continue
        actualizar(path)
        print(path.parent.name)
