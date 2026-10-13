"""Genera cuatro agentes Huawei SNMPv3 a partir de los MIB locales.

Los valores son datos de laboratorio. Los OID se resuelven desde los MIB, no
se asignan números arbitrarios a atributos del fabricante.
"""
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
MIBS = ROOT / "mibs" / "huawei"
DATA = ROOT / "data"
ENTERPRISES = "1.3.6.1.4.1"


class Mib:
    def __init__(self, content, seeds=None):
        self.defs = {
            name: (parent, int(number))
            for name, parent, number in re.findall(
                r"(?m)^\s*([\w-]+)\s+(?:OBJECT IDENTIFIER|MODULE-IDENTITY|OBJECT-TYPE)\b"
                r"[\s\S]*?::=\s*\{\s*([\w-]+)\s+(\d+)\s*\}", content
            ) if name != "IMPORTS"
        }
        self.seeds = {"enterprises": ENTERPRISES, **(seeds or {})}
        self.syntax = {}
        self.access = {}
        for match in re.finditer(r"(?m)^\s*([\w-]+)\s+OBJECT-TYPE\b([\s\S]*?)::=", content):
            syntax = re.search(r"\bSYNTAX\s+(OCTET STRING|[\w-]+)", match.group(2))
            if syntax:
                self.syntax[match.group(1)] = syntax.group(1)
            access = re.search(r"\bMAX-ACCESS\s+([\w-]+)", match.group(2))
            if access:
                self.access[match.group(1)] = access.group(1)

    def oid(self, symbol):
        parts = []
        seen = set()
        while symbol not in self.seeds:
            if symbol in seen or symbol not in self.defs:
                raise ValueError(f"No se puede resolver el OID de {symbol}")
            seen.add(symbol)
            symbol, number = self.defs[symbol]
            parts.append(str(number))
        return ".".join((self.seeds[symbol], *reversed(parts)))


def from_zip(pattern, member, seeds=None):
    path = next(MIBS.rglob(pattern))
    with zipfile.ZipFile(path) as archive:
        return Mib(archive.read(member).decode("latin-1"), seeds)


def from_file(pattern, seeds=None):
    path = next(MIBS.rglob(pattern))
    return Mib(path.read_bytes().decode("latin-1"), seeds)


def rows():
    return {}


def put(data, oid, tag, value):
    if oid in data:
        raise ValueError(f"OID duplicado: {oid}")
    data[oid] = (tag, str(value))


def vendor(data, mib, symbol, value, tag="4", index=None):
    if mib.access.get(symbol) == "not-accessible":
        return
    expected = {"DisplayString": "4", "OCTET STRING": "4", "INTEGER": "2",
                "Integer32": "2", "Unsigned32": "66", "Gauge32": "66",
                "Counter32": "65", "Counter64": "70", "OBJECT IDENTIFIER": "6"}
    syntax = mib.syntax.get(symbol)
    # La declaración del MIB prevalece sobre el tipo sugerido en la muestra.
    if syntax in expected:
        tag = expected[syntax]
    base = mib.oid(symbol)
    oid = base + (".0" if index is None else "." + str(index))
    put(data, oid, tag, value)


def system(data, hostname, description, object_id, location):
    values = [
        ("1.3.6.1.2.1.1.1.0", "4", description),
        ("1.3.6.1.2.1.1.2.0", "6", object_id),
        ("1.3.6.1.2.1.1.3.0", "67", 8640000),
        ("1.3.6.1.2.1.1.5.0", "4", hostname),
        ("1.3.6.1.2.1.1.6.0", "4", location),
        ("1.3.6.1.2.1.1.7.0", "2", 76),
    ]
    for oid, tag, value in values:
        put(data, oid, tag, value)


def interfaces(data, ports):
    put(data, "1.3.6.1.2.1.2.1.0", "2", len(ports))
    for index, (name, mac, speed) in enumerate(ports, 1):
        prefix = "1.3.6.1.2.1.2.2.1"
        for column, tag, value in [
            (1, "2", index), (2, "4", name), (3, "2", 6),
            (5, "66", min(speed, 4294967295)), (6, "4x", mac.replace(":", "")),
            (7, "2", 1), (8, "2", 1),
            (10, "65", 120000 * index), (16, "65", 90000 * index),
        ]:
            put(data, f"{prefix}.{column}.{index}", tag, value)
        xprefix = "1.3.6.1.2.1.31.1.1.1"
        for column, tag, value in [
            (1, "4", name), (6, "70", 4100000000 * index),
            (10, "70", 3200000000 * index), (15, "66", speed // 1000000),
        ]:
            put(data, f"{xprefix}.{column}.{index}", tag, value)


def ibmc(data, mib, hostname, serial, model, slot=None, *, instancia=None,
         serie_chasis=None, ubicacion=None):
    instancia = (1 if slot else 0) if instancia is None else instancia
    system(data, hostname, f"Huawei {model} iBMC", mib.oid("hwiBMC"),
           ubicacion or ("DC-LAB-HUAWEI / E9000 Bay 1" if slot else
                         "DC-LAB-HUAWEI / Rack H01"))
    for symbol, tag, value in [
        ("systemHealth", "2", 1), ("deviceName", "4", model),
        ("deviceSerialNo", "4", serial), ("hostName", "4", hostname),
        ("systemPowerState", "2", 2), ("presentSystemPower", "2", 360 if slot else 620),
        ("systemCpuUsage", "2", 24 if slot else 31),
        ("systemMemUsage", "2", 38 if slot else 46),
    ]:
        vendor(data, mib, symbol, value, tag)
    if slot:
        vendor(data, mib, "deviceslotID", slot, "4")
        vendor(data, mib, "shelfChassisID", 1, "2")
        vendor(data, mib, "shelfType", "E9000")
        vendor(data, mib, "shelfSerialNumber", serie_chasis or "HWE9000LAB001")
    for index in (1, 2):
        cpu = "Intel Xeon E5-2698 v4" if slot else "Intel Xeon Gold 6226R"
        for symbol, tag, value in [
            ("cpuIndex", "2", index), ("cpuManufacturer", "4", "Intel"),
            ("cpuFamily", "4", "Xeon"), ("cpuType", "4", cpu),
            ("cpuClockRate", "4", f"{2200 if slot else 2900} MHz"),
            ("cpuStatus", "2", 1), ("cpuDevicename", "4", f"CPU{index}"),
            ("cpuCoreCount", "2", 20 if slot else 16),
            ("cpuThreadCount", "2", 40 if slot else 32),
        ]:
            vendor(data, mib, symbol, value, tag, index)
    for index, decimas in enumerate((430, 450) if slot else (480, 500), 1):
        vendor(data, mib, "temperatureIndex", index, "2", index)
        vendor(data, mib, "temperatureReading", decimas, "2", index)
    for symbol, tag, value in [
        ("raidControllerIndex", "2", 1),
        ("raidControllerName", "4", "RAID Controller 1"),
        ("raidControllerType", "4", "Huawei RAID Controller CH121 V5" if slot else
         "Huawei RAID Controller 2288H V5"),
        ("raidControllerHealthStatus", "2", 0),
    ]:
        vendor(data, mib, symbol, value, tag, 1)
    for index, level in enumerate(("RAID1",) if slot else ("RAID1", "RAID5"), 1):
        vendor(data, mib, "logicalDriveRAIDLevel", level, "4", f"1.{index}")
    for index in range(1, 5):
        for symbol, tag, value in [
            ("memoryDimmIndex", "2", index), ("memoryManufacturer", "4", "Samsung"),
            ("memorySize", "4", f"{16 if slot else 32} GB"),
            ("memoryClockRate", "4", f"{2400 if slot else 2933} MHz"),
            ("memoryStatus", "2", 1), ("memoryDevicename", "4", f"DIMM{index}"),
            ("memoryType", "4", "DDR4"),
            ("memorySN", "4", f"HWRAM{instancia}{index:04d}"),
        ]:
            vendor(data, mib, symbol, value, tag, index)
    for index in range(1, 3 if slot else 5):
        for symbol, tag, value in [
            ("hardDiskIndex", "2", index), ("hardDiskPresence", "2", 2),
            ("hardDiskStatus", "2", 1), ("hardDiskLocation", "4", f"Bay {index}"),
            ("hardDiskSerialNumber", "4", f"HWSSD{instancia}{index:04d}"),
            ("hardDiskModelNumber", "4", "Huawei 960GB SAS SSD"),
            ("hardDiskManufacturer", "4", "Huawei"),
            ("hardDiskCapacityInGB", "2", 960),
            ("hardDiskTemperature", "2", 29 + index),
        ]:
            vendor(data, mib, symbol, value, tag, index)
    if not slot:
        for index in (1, 2):
            for symbol, tag, value in [
                ("powerSupplyIndex", "2", index),
                ("powerSupplymanufacture", "4", "Huawei"),
                ("powerSupplyInputMode", "2", 1),
                ("powerSupplyModel", "4", "Huawei 900W AC PSU"),
                ("powerSupplyPowerRating", "2", 900),
                ("powerSupplyStatus", "2", 1),
                ("powerSupplySN", "4", f"HWPSU{instancia}{index:04d}" if instancia else f"HWPSU{index:04d}"),
            ]:
                vendor(data, mib, symbol, value, tag, index)
        for index in range(1, 5):
            for symbol, tag, value in [
                ("fanIndex", "2", index), ("fanSpeed", "2", 8500 + index * 200),
                ("fanStatus", "2", 1), ("fanDevicename", "4", "BC1M05FAN"),
            ]:
                vendor(data, mib, symbol, value, tag, index)
    for index in (1, 2):
        for symbol, tag, value in [
            ("netCardIndex", "2", index),
            ("netCardNICModel", "4", "Huawei 10Gb Ethernet Adapter"),
            ("netCardNICName", "4", f"HWNIC{instancia}{index:04d}"),
            ("netCardNICManufacturer", "4", "Huawei"),
            ("netCardStatus", "2", 1),
        ]:
            vendor(data, mib, symbol, value, tag, index)
    mac_instancia = max(0, instancia - 1)
    interfaces(data, [("eth1", f"02:48:57:10:{mac_instancia:02x}:01", 1000000000),
                      ("eth2", f"02:48:57:10:{mac_instancia:02x}:02", 10000000000)])


def e9000(data, mib, *, instancia=1, serie_blade="HWCH121V5001"):
    hostname = f"huawei-e9000-{instancia:02d}"
    serie = f"HWE9000LAB{instancia:03d}"
    system(data, hostname, "Huawei E9000 Blade Server Chassis MM910",
           mib.oid("hwSMM"), f"DC-LAB-HUAWEI / Rack H{2 if instancia == 1 else 5:02d}")
    for symbol, tag, value in [
        ("systemHealth", "2", 0), ("shelfHealth", "2", 0),
        ("shelfChassisName", "4", hostname),
        ("shelfChassisID", "4", f"E9000-{instancia:02d}"),
        ("shelfRealTimePower", "2", 1760), ("shelfOutletTemp", "2", 27),
    ]:
        vendor(data, mib, symbol, value, tag)
    for symbol, tag, value in [
        ("shelfNumber", "2", 1), ("shelfPartNumber", "4", "E9000"),
        ("shelfSerialNumber", "4", serie),
        ("shelfType", "4", "E9000"),
    ]:
        vendor(data, mib, symbol, value, tag, 1)
    for blade in (1, 2):
        for symbol, tag, value in [
            (f"b{blade}Presence", "2", 1 if blade == 1 else 0),
            (f"b{blade}PowerState", "4", "poweron" if blade == 1 else "poweroff"),
            (f"b{blade}Health", "2", 0),
        ]:
            vendor(data, mib, symbol, value, tag)
    vendor(data, mib, "b1ProductName", "CH121 V5")
    vendor(data, mib, "b1fruProductSerialNumber", serie_blade, index=1)
    for index in (1, 2):
        for symbol, tag, value in [
            ("mPsuIndex", "2", index), ("mPsuLocation", "2", index),
            ("mPsuHealth", "2", 1),
        ]:
            vendor(data, mib, symbol, value, tag, index)
        for symbol, tag, value in [
            ("powerPresence", "2", 1), ("powerState", "2", 0),
            ("powerRatingPower", "4", "2000W"),
            ("powerInfo", "4", "Huawei E9000 2000W AC PSU"),
        ]:
            vendor(data, mib, symbol, value, tag, index)
    for index in range(1, 5):
        for symbol, tag, value in [
            ("fanIndex", "2", index), ("fanPresence", "2", 1),
            ("fanSpeed", "4", "65"),
            ("fanInfo", "4", "Huawei E9000 fan module (simulado)"),
            ("fanStatus", "2", 0),
        ]:
            vendor(data, mib, symbol, value, tag, index)
    vendor(data, mib, "fanTrayHealth", 0, "2")
    vendor(data, mib, "smmTemperatureIndex", 1, "2", 1)
    vendor(data, mib, "smmTemperatureReading", 27, "2", 1)
    interfaces(data, [("MM910 uplink 1", f"02:48:57:90:{instancia - 1:02x}:01", 10000000000),
                      ("MM910 uplink 2", f"02:48:57:90:{instancia - 1:02x}:02", 10000000000)])


def dorado(data, svc, hw, space, perf, *, instancia=1):
    codigo = "" if instancia == 1 else str(instancia)
    system(data, f"huawei-dorado-{instancia:02d}", "Huawei OceanStor Dorado 5000 V6",
           svc.oid("hwISM"), f"DC-LAB-HUAWEI / Rack H{3 if instancia == 1 else 6:02d}")
    for symbol, tag, value in [
        ("deviceId", "4", f"HWDORADO5000V6{instancia:03d}"),
        ("usedCapacity", "70", 10_485_760),
        ("totalCapacity", "70", 20_971_520),
        ("version", "4", "6.1.6"),
    ]:
        vendor(data, svc, symbol, value, tag)
    for index in (1, 2):
        for symbol, tag, value in [
            ("hwStorageControllerID", "66", index),
            ("hwStorageControllerMemorySize", "66", 131072),
            ("hwStorageControllerCPUInfo", "4",
             "Huawei;OceanStor;Dorado Controller CPU (simulado);2.4 GHz"),
        ]:
            vendor(data, svc, symbol, value, tag, index)
        for symbol, tag, value in [
            ("hwInfoControllerID", "66", index),
            ("hwInfoControllerHealthStatus", "66", 1),
            ("hwInfoControllerRunningStatus", "66", 2),
            ("hwInfoControllerLocation", "4", f"Controller {index}"),
            ("hwInfoControllerElectronicLabel", "4",
             f"SN=HWDCTRL{codigo}{index:04d};MODEL=Dorado 5000 V6 Controller (simulado)"),
            ("hwInfoControllerCacheCapacity", "70", 131072),
            ("hwInfoControllerCPUUsage", "66", 28 + index),
            ("hwInfoControllerMemoryUsage", "66", 43 + index),
        ]:
            vendor(data, hw, symbol, value, tag, index)
    # Sensores estándar de laboratorio. El MIB propietario Dorado solo da
    # nivel de ventilador y no incluye consumo actual en W ni RPM.
    for sensor_index, name, sensor_type, value in [
        (100, "Storage total power", 6, 1180 if instancia == 1 else 1240),
        (201, "Fan 1 RPM", 10, 6200),
        (202, "Fan 2 RPM", 10, 6300),
        (203, "Fan 3 RPM", 10, 6150),
        (204, "Fan 4 RPM", 10, 6250),
    ]:
        put(data, f"1.3.6.1.2.1.47.1.1.1.1.7.{sensor_index}", "4", name)
        for field, field_value in [(1, sensor_type), (2, 9), (3, 0),
                                   (4, value), (5, 1)]:
            put(data, f"1.3.6.1.2.1.99.1.1.1.{field}.{sensor_index}",
                "2", field_value)
    for index in range(1, 7):
        for symbol, tag, value in [
            ("hwInfoDiskID", "66", index),
            ("hwInfoDiskHealthStatus", "66", 1),
            ("hwInfoDiskRunningStatus", "66", 2),
            ("hwInfoDiskType", "66", 14),
            ("hwInfoDiskCapacity", "70", 3_686_400),
            ("hwInfoDiskTemperature", "66", 30 + index),
            ("hwInfoDiskModel", "4", "Huawei 3.84TB NVMe SSD"),
            ("hwInfoDiskManufacturer", "4", "Huawei"),
            ("hwInfoDiskSerialNumber", "4", f"HWDSSD{codigo}{index:04d}"),
        ]:
            vendor(data, hw, symbol, value, tag, index)
    for index in (1, 2):
        for symbol, tag, value in [
            ("hwInfoPowerID", "66", index),
            ("hwInfoPowerHealthStatus", "66", 1),
            ("hwInfoPowerRunningStatus", "66", 2),
            ("hwInfoPowerType", "66", 1),
            ("hwInfoPowerManufacturer", "4", "Huawei"),
            ("hwInfoPowerModle", "4", "Huawei 2000W AC PSU"),
            ("hwInfoPowerSerialNumber", "4", f"HWDPSU{codigo}{index:04d}"),
        ]:
            vendor(data, hw, symbol, value, tag, index)
    for index in range(1, 5):
        for symbol, tag, value in [
            ("hwInfoFanID", "66", index),
            ("hwInfoFanHealthStatus", "66", 1),
            ("hwInfoFanRunningStatus", "66", 2),
            ("hwInfoFanRunningLevel", "66", 1),
            ("hwInfoFanElectronicLabel", "4",
             f"SN=HWDFAN{codigo}{index:04d};MODEL=Dorado Fan Module (simulado)"),
        ]:
            vendor(data, hw, symbol, value, tag, index)
    for symbol, tag, value in [
        ("hwInfoStoragePoolID", "66", 1),
        ("hwInfoStoragePoolName", "4", "pool-produccion"),
        ("hwInfoStoragePoolHealthStatus", "66", 1),
        ("hwInfoStoragePoolRunningStatus", "66", 2),
        ("hwInfoStoragePoolTotalCapacity", "70", 20_971_520),
        ("hwInfoStoragePoolFreeCapacity", "70", 10_485_760),
    ]:
        vendor(data, space, symbol, value, tag, 1)
    for symbol, tag, value in [
        ("hwInfoLunID", "4", "1"),
        ("hwInfoLunName", "4", "lun-aplicaciones"),
        ("hwInfoLunPoolID", "4", "1"),
        ("hwInfoLunCapacity", "70", 4_194_304),
        ("hwInfoLunHealthStatus", "66", 1),
        ("hwInfoLunRunningStatus", "66", 2),
    ]:
        vendor(data, space, symbol, value, tag, 1)
    for index in (1, 2):
        for symbol, tag, value in [
            ("hwStorageFCPortIfIndex", "2", index),
            ("hwStorageFCPortID", "66", index),
            ("hwStorageFCPortStatus", "2", 1),
            ("hwStorageFCPortWWN", "4", f"50060E80{instancia}000000{index}"),
            ("hwStorageFCPortSpeedRate", "2", 16),
        ]:
            vendor(data, svc, symbol, value, tag, index)
    for index in (1, 2):
        for symbol, tag, value in [
            ("hwPerfNodeIfIndex", "66", index),
            ("hwPerfNodeCPUUsage", "66", 29 + index),
            ("hwPerfNodeDelay", "66", 2),
            ("hwPerfNodeTotalIOPS", "66", 12000 + index * 500),
            ("hwPerfNodeReadIOPS", "66", 8000 + index * 300),
            ("hwPerfNodeWriteIOPS", "66", 4000 + index * 200),
        ]:
            vendor(data, perf, symbol, value, tag, index)


def save(name, data):
    folder = DATA / name
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f"{oid}|{tag}|{value}" for oid, (tag, value) in sorted(
        data.items(), key=lambda item: tuple(map(int, item[0].split("."))))]
    (folder / "public.snmprec").write_text("\n".join(lines) + "\n", encoding="ascii")
    print(name, len(lines), "OID")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo", nargs="+", choices=(
        "huawei-2288h-v5-01", "huawei-2288h-v5-02",
        "huawei-ch121-v5-01", "huawei-ch121-v5-02",
        "huawei-e9000-01", "huawei-e9000-02",
        "huawei-dorado-01", "huawei-dorado-02"))
    args = parser.parse_args()
    ibmc_file = "HUAWEI-SERVER-iBMC-MIB.mib"
    rack = from_zip("*V502.zip", ibmc_file, {"huawei": ENTERPRISES + ".2011"})
    blade = from_zip("*V670.zip", ibmc_file, {"huawei": ENTERPRISES + ".2011"})
    chassis = from_zip("MM910-MIB-V763.zip", "OSCA-MIB.mib")
    dorado_root = next(MIBS.glob("OceanStor Dorado*")) / "MIB Files"
    seeds = {"huaweistorage": ENTERPRISES + ".34774",
             "hwStorage": ENTERPRISES + ".34774.4",
             "hwISM": ENTERPRISES + ".34774.4.1"}
    svc = Mib((dorado_root / "ISM-STORAGE-SVC-MIB.mib").read_bytes().decode("latin-1"), seeds)
    hw = Mib((dorado_root / "HUAWEI-STORAGE-HARDWARE-MIB.mib").read_bytes().decode("latin-1"), seeds)
    space = Mib((dorado_root / "HUAWEI-STORAGE-SPACE-MIB.mib").read_bytes().decode("latin-1"), seeds)
    perf = Mib((dorado_root / "ISM-PERFORMANCE-MIB.mib").read_bytes().decode("latin-1"), seeds)
    profiles = [
        ("huawei-2288h-v5-01", lambda d: ibmc(d, rack, "huawei-2288h-v5-01", "HW2288HV5001", "FusionServer Pro 2288H V5")),
        ("huawei-2288h-v5-02", lambda d: ibmc(d, rack, "huawei-2288h-v5-02", "HW2288HV5002", "FusionServer Pro 2288H V5", instancia=2, ubicacion="DC-LAB-HUAWEI / Rack H04")),
        ("huawei-ch121-v5-01", lambda d: ibmc(d, blade, "huawei-ch121-v5-01", "HWCH121V5001", "CH121 V5", 1)),
        ("huawei-ch121-v5-02", lambda d: ibmc(d, blade, "huawei-ch121-v5-02", "HWCH121V5002", "CH121 V5", 1, instancia=3, serie_chasis="HWE9000LAB002", ubicacion="DC-LAB-HUAWEI / E9000-02 Bay 1")),
        ("huawei-e9000-01", lambda d: e9000(d, chassis)),
        ("huawei-e9000-02", lambda d: e9000(d, chassis, instancia=2, serie_blade="HWCH121V5002")),
        ("huawei-dorado-01", lambda d: dorado(d, svc, hw, space, perf)),
        ("huawei-dorado-02", lambda d: dorado(d, svc, hw, space, perf, instancia=2)),
    ]
    for name, fill in profiles:
        if args.solo and name not in args.solo:
            continue
        data = rows()
        fill(data)
        save(name, data)


if __name__ == "__main__":
    main()
