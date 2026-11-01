"""Ocupación de volúmenes: CPQHOST-MIB y HOST-RESOURCES-MIB (solo disco fijo)."""
from decimal import Decimal
from etl.oid_util import filas, numero

CPQ="1.3.6.1.4.1.232.11.2.4.1.1"
HR="1.3.6.1.2.1.25.2.3.1"


def uso_disco(datos, fabricante):
    if fabricante=="HPE":
        volumenes=filas(datos,{"total":CPQ+".3","usado":CPQ+".4"})
        if volumenes:
            valores=[]
            for _,v in volumenes:
                total,usado=numero(v.get("total")),numero(v.get("usado"))
                if total is None or usado is None or not 0<=usado<=total:return []
                valores.append(Decimal(usado)/1024)
            return [{"nombre_metrica":"disco_uso_gb","valor":sum(valores)}]
    volumenes=filas(datos,{"tipo":HR+".2","unidad":HR+".4","total":HR+".5","usado":HR+".6"})
    valores=[]
    for _,v in volumenes:
        if str(v.get("tipo"))!="1.3.6.1.2.1.25.2.1.4":continue
        unidad,total,usado=(numero(v.get(c)) for c in ("unidad","total","usado"))
        if unidad is None or unidad<=0 or total is None or usado is None or not 0<=usado<=total:return []
        valores.append(Decimal(usado)*unidad/(1024**3))
    return [{"nombre_metrica":"disco_uso_gb","valor":sum(valores)}] if valores else []
