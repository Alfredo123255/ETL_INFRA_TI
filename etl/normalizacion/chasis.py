"""Ficha de chasis blade HPE y sus slots, energía e interconexiones."""
import re
from etl.errores import DatosIncompletos, PerfilNoSoportado
from etl.normalizacion.servidor import _s, _n, _estado, _base, _puertos, _mediciones
from etl.oid_util import SYSTEM, filas, texto, numero
from etl.normalizacion.estados import CONDICION_HPE, normalizar_estado
from etl.normalizacion.inferencias import corriente_desde_voltaje, potencia_nominal_modelo

BASE="1.3.6.1.4.1.232.22.2"
C=BASE+".3.1.1.1"
S=BASE+".4.1.1.1"
F=BASE+".3.1.3.1"
P=BASE+".5.1.1.1"
N=BASE+".6.1.1.1"
IF="1.3.6.1.2.1.2.2.1"
IFX="1.3.6.1.2.1.31.1.1.1"

def normalizar_chasis_hpe(datos, *, fecha_actualizacion):
    enclosures=filas(datos,{"modelo":C+".3","serie":C+".7","firmware":C+".8",
                            "hostname":C+".9","estado":C+".16"})
    if len(enclosures)!=1:
        raise DatosIncompletos("El chasis no proporciona una identidad única.")
    e=enclosures[0][1]
    serie,modelo=texto(e.get("serie")),texto(e.get("modelo"))
    hostname=texto(e.get("hostname")) or texto(datos.get(SYSTEM["hostname"]))
    if not serie or not modelo or not hostname:
        raise DatosIncompletos("Falta hostname, serie o modelo del chasis.")
    slots=[]
    for _,s in filas(datos,{"numero_slot":S+".8","presente":S+".12", "estado":S+".21", "hostname":S+".4"}):
        present=numero(s.get("presente")); state=numero(s.get("estado"))
        status="LIBRE" if present!=3 else "OCUPADO" if state==2 else "DEGRADADO"
        slots.append({"numero_slot":numero(s.get("numero_slot")),"estado":status,
            "hostname_servidor":texto(s.get("hostname")) if status!="LIBRE" else None})
    capacity=filas(datos,{"max":BASE+".3.2.1.1.4"})
    max_slots=numero(capacity[0][1].get("max")) if capacity else None
    if max_slots is None or max_slots<len(slots) or not slots:
        raise DatosIncompletos("La capacidad de slots del chasis es inválida.")
    fans=[]
    for _,f in filas(datos,{"modelo":F+".6","estado":F+".11"}):
        fans.append({"numero_serial":None,"modelo":texto(f.get("modelo")),"velocidad_rpm":None,
            "estado":normalizar_estado(numero(f.get("estado")),CONDICION_HPE)})
    # En este perfil hay un único chasis. La entrada del dominio de energía
    # se aplica a sus fuentes solo si todos los dominios del rack concuerdan.
    tipos_por_rack={}
    for indice,f in filas(datos,{"tipo":BASE+".3.3.1.1.7"}):
        rack=indice.split(".")[0]
        tipos_por_rack.setdefault(rack,[]).append({2:"AC",3:"AC",4:"DC"}.get(numero(f.get("tipo"))))
    corriente_por_rack={rack:valores[0] if len(set(valores))==1 else None
                        for rack,valores in tipos_por_rack.items()}
    fuentes=[]
    for indice,f in filas(datos,{"serie":P+".5","modelo":P+".6","capacidad_max_w":P+".9","estado":P+".17"}):
        capacidad = numero(f.get("capacidad_max_w"))
        fuentes.append({"numero_serial":texto(f.get("serie")),"modelo":texto(f.get("modelo")),
            "consumo_w":capacidad if capacidad is not None and capacidad > 0 else None,
            "tipo_corriente":corriente_por_rack.get(indice.split(".")[0]),
            "estado":normalizar_estado(numero(f.get("estado")),CONDICION_HPE)})
    network=[]
    interfaces={}
    for idx,port in filas(datos,{"name":IFX+".1","speed":IFX+".15","oper":IF+".8"}):
        ifname=texto(port.get("name"))
        if ifname and re.fullmatch(r"[Xd]\d+",ifname):
            interfaces[idx]={"numero_puerto":ifname,"mac_address":None,
                "velocidad":f"{numero(port['speed'])} Mbps" if numero(port.get("speed")) else None,
                "estado":"Encendido" if numero(port.get("oper"))==1 else "Apagado"}
    for index,(_,n) in enumerate(filas(datos,{"modelo":N+".6","serie":N+".7","presente":N+".11"})):
        # El simulador sólo atribuye puertos IF-MIB al primer módulo Virtual Connect.
        ports=list(interfaces.values()) if index==0 else []
        modelo_red=texto(n.get("modelo"))
        network.append({"numero_serial":texto(n.get("serie")),
            "marca":"HPE" if modelo_red and re.match(r"^HPE\b",modelo_red,re.I) else None,
            "modelo":modelo_red,
            "estado":"Encendido" if numero(n.get("presente"))==3 else "Apagado",
            "cantidad_puertos":len(ports),"puertos":ports})
    temps=filas(datos,{"valor":BASE+".3.1.2.1.6"})
    temperature=numero(temps[0][1].get("valor")) if temps else None
    meters=filas(datos,{"watts":BASE+".5.2.1.1.8"})
    power=numero(meters[0][1].get("watts")) if meters else None
    gen=re.search(r"\bG\d+\b",modelo,re.I)
    activo={"numero_serie":serie,"hostname":hostname,"fabricante":"HPE","modelo":modelo,
        "generacion":gen.group() if gen else None,"tipo_activo":"CHASIS",
        "estado_operativo":normalizar_estado(numero(e.get("estado")),CONDICION_HPE),
        "version_firmware":texto(e.get("firmware")),"ultima_actualizacion":fecha_actualizacion,
        "temperatura":temperature,"consumo_electrico_w":power}
    mediciones=[{"nombre_metrica":name,"valor":value} for name,value in
        (("temperatura",temperature),("consumo_electrico_w",power)) if value is not None]
    return {"activo":activo,"chasis_blade":{"cantidad_slots":max_slots},
        "componentes":{"chasis_slot":slots,"ventilador":fans,"fuente_poder":fuentes,"tarjeta_red":network},
        "mediciones":mediciones,"ubicacion_snmp":texto(datos.get(SYSTEM["ubicacion"]))}


E9000 = "1.3.6.1.4.1.2011.2.82.1.82"

def normalizar_chasis_huawei(datos, *, fecha_actualizacion):
    d = E9000
    serie = _s(datos, d + ".2.2001.1.15.1")
    modelo = _s(datos, d + ".2.2001.1.16.1") or _s(datos, d + ".2.2001.1.14.1")
    activo = _base(serie, _s(datos, d + ".2.18.0") or _s(datos, SYSTEM["hostname"]),
                   modelo, "CHASIS", _estado(_n(datos, d + ".2.5.0"), cero_bien=True),
                   fecha_actualizacion, temperatura=_n(datos, d + ".2.24.0"),
                   consumo=_n(datos, d + ".2.13.0"))
    slots = []
    # OSCA-MIB define las bahías como objetos b1..bN, no como tabla dinámica.
    for bahia in range(1, 17):
        raiz = f"{d}.4.{bahia}"
        presente = _n(datos, raiz + ".6.0")
        if presente is None:
            continue
        salud = _n(datos, raiz + ".8.0")
        slots.append({"numero_slot": bahia,
                      "estado": "LIBRE" if presente == 0 else
                                "OCUPADO" if salud == 0 else "DEGRADADO",
                      "hostname_servidor": None,
                      "serie_servidor": _s(datos, raiz + ".2004.1.10.1") if presente else None})
    if not slots:
        raise DatosIncompletos("El chasis Huawei no expone bahías reconocibles.")
    ventiladores = [{"numero_serial": None, "modelo": texto(f.get("info")), "velocidad_rpm": None,
                    "estado": _estado(numero(f.get("estado")), cero_bien=True)}
                    for _, f in filas(datos, {"info": d + ".5.2001.1.4",
                                             "estado": d + ".5.2001.1.7"})]
    # pemsPowerTable expone la potencia nominal y la etiqueta FRU de cada PSU.
    # La tabla de gestión solo aporta la salud y sirve de respaldo si falta FRU.
    gestion = dict(filas(datos, {"salud": d + ".100.4.2001.1.3"}))
    energia = dict(filas(datos, {"presente": d + ".6.2001.1.2",
                               "estado": d + ".6.2001.1.3",
                               "potencia": d + ".6.2001.1.4",
                               "modo": d + ".6.2001.1.5",
                               "info": d + ".6.2001.1.7"}))
    fuentes = []
    for indice in sorted(set(gestion) | set(energia), key=lambda x: tuple(map(int, x.split(".")))):
        f = energia.get(indice, {})
        descripcion = texto(f.get("info"))
        potencia = texto(f.get("potencia"))
        nominal = re.fullmatch(r"\s*(\d{2,5})\s*(?:W|watts)?\s*", potencia, re.I) if potencia else None
        capacidad = int(nominal.group(1)) if nominal else potencia_nominal_modelo(descripcion)
        presente, estado = numero(f.get("presente")), numero(f.get("estado"))
        salud = numero(gestion.get(indice, {}).get("salud"))
        estado_normalizado = ("Apagado" if presente == 0 else
                              "Encendido" if presente == 1 and estado == 0 else
                              "Degradado" if estado == 1 else _estado(salud))
        fuentes.append({"numero_serial": None, "modelo": descripcion or f"PSU {indice}",
                        "consumo_w": capacidad if capacidad and capacidad > 0 else None,
                        "tipo_corriente": corriente_desde_voltaje(descripcion) or
                                           corriente_desde_voltaje(texto(f.get("modo"))),
                        "estado": estado_normalizado})
    puertos = _puertos(datos)
    tarjetas = [{"numero_serial": None, "marca": "Huawei", "modelo": "MM910 uplink",
                 "estado": "Encendido" if any(p["estado"] == "Encendido" for p in puertos) else "Apagado",
                 "cantidad_puertos": len(puertos), "puertos": puertos}] if puertos else []
    return {"activo": activo, "chasis_blade": {"cantidad_slots": len(slots)},
            "componentes": {"chasis_slot": slots, "ventilador": ventiladores,
                            "fuente_poder": fuentes, "tarjeta_red": tarjetas},
            "mediciones": _mediciones(activo), "ubicacion_snmp": _s(datos, SYSTEM["ubicacion"])}




def normalizar_chasis(datos, *, fecha_actualizacion, fabricante="HPE"):
    perfiles = {"HPE": normalizar_chasis_hpe, "Huawei": normalizar_chasis_huawei}
    if fabricante not in perfiles:
        raise PerfilNoSoportado("Fabricante de chasis sin perfil implementado.")
    return perfiles[fabricante](datos, fecha_actualizacion=fecha_actualizacion)
