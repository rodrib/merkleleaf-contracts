import hashlib
import time

from src import ForestRegistry

# ---------------------------------------------------------------------------
# Datos de campo: parcela Gran Chaco (Quebracho), coordenadas ya convertidas
# de DMS a grados decimales * 1e6, y biometria escalada a enteros:
#   dap_mm  -> diametro a la altura del pecho, en milimetros
#   hf_cm   -> altura de fuste, en centimetros
#   ht_cm   -> altura total, en centimetros
#
# OJO: la planilla original decia "DAP (m)" pero valores como 30,5 o 51,3
# no tienen sentido como metros de diametro de tronco -> se asumieron como
# CENTIMETROS (estandar forestal para DAP). Si en realidad son otra unidad,
# ajusta el factor de escala dap_mm = dap * 10 mas abajo antes de correr esto.
# ---------------------------------------------------------------------------

SAMPLES = [
    # name,          lat_e6,     lon_e6,     dap_mm, hf_cm, ht_cm
    ("QUEBRA 1",  -25917750, -58376806, 305, 830, 1600),
    ("QUEBRA 2",  -25917778, -58376833, 350, 800, 1600),
    ("QUEBRA 3",  -25917861, -58376806, 270, 730, 1400),
    ("QUEBRA 4",  -25918000, -58376778, 513, 390, 1400),
    ("QUEBRA 5",  -25918000, -58376778, 414, 840, 1700),
    ("QUEBRA 6",  -25917972, -58376667, 384, 600, 1550),
    ("QUEBRA 7",  -25917889, -58376583, 293, 1500, 2200),
    ("QUEBRA 8",  -25918000, -58376639, 323, 1200, 1800),
    ("QUEBRA 9",  -25918056, -58376639, 307, 1300, 1900),
    ("QUEBRA 10", -25918083, -58376583, 354, 1300, 1900),
    ("QUEBRA 11", -25918139, -58376611, 410, 1500, 2000),
    ("QUEBRA 12", -25918167, -58376361, 416, 780, 2200),
    ("QUEBRA 13", -25918194, -58376361, 286, 1300, 1800),
    ("QUEBRA 14", -25918333, -58376944, 371, 1600, 2300),
    ("QUEBRA 15", -25918556, -58376972, 694, 1400, 2500),
    ("QUEBRA 16", -25918583, -58377167, 526, 780, 1800),
    ("QUEBRA 17", -25919083, -58376889, 653, 1400, 2800),
    ("QUEBRA 18", -25919500, -58376417, 462, 1000, 1800),
    ("QUEBRA 19", -25917833, -58376944, 528, 850, 1600),
    ("QUEBRA 20", -25917806, -58376917, 285, 650, 1500),
    ("QUEBRA 21", -25917667, -58376528, 369, 1100, 1800),
    ("QUEBRA 22", -25917583, -58376944, 480, 330, 1400),
    ("QUEBRA 23", -25917667, -58376444, 418, 1000, 1800),
]

# Placeholder hasta tener el índice NDVI real por árbol/parcela (teledetección).
# 0 = "sin dato cargado todavía". Reemplazar por el valor real * 1e4 cuando
# esté disponible (ej. NDVI 0.72 -> 7200).
DEFAULT_NDVI_E4 = 0
DEFAULT_SPECTRAL_SOURCE = "Pendiente de carga (Sentinel-2 L2A)"

# Espera entre transacciones: le da tiempo a la RPC de indexar el bloque
# recien minado antes de mandar la siguiente transaccion.
SECONDS_BETWEEN_TXNS = 6

# Mensajes que identifican el error de "resync local" que ocurre DESPUES
# de que la transaccion ya fue minada exitosamente on-chain. En ese caso
# NO hay que reenviar la transaccion (reenviar duplicaria el registro).
BENIGN_RESYNC_ERROR_SNIPPETS = (
    "Unknown block number",
    "NoneType' object is not subscriptable",
)


def field_hash(name: str, dap_mm: int, hf_cm: int, ht_cm: int) -> bytes:
    """
    Hash de referencia de los datos de campo crudos de cada árbol.
    Sirve como huella para verificar después que el registro on-chain
    corresponde a la planilla/foto original. Reemplazar por el hash real
    del archivo de campo (CSV, foto georreferenciada, etc.) cuando se
    integre el pipeline completo.
    """
    raw = f"{name}|{dap_mm}|{hf_cm}|{ht_cm}".encode()
    return hashlib.sha256(raw).digest()


def _is_benign_resync_error(exc: Exception) -> bool:
    text = str(exc)
    return any(snippet in text for snippet in BENIGN_RESYNC_ERROR_SNIPPETS)


def deploy_with_resync_tolerance():
    """
    Igual que ForestRegistry.deploy(), pero si el UNICO problema es el
    resync local post-mineo (la tx de deploy ya se confirmo on-chain),
    no reintenta el deploy (evita desplegar contratos duplicados).
    Solo reintenta si el deploy realmente no llego a broadcastearse.
    """
    try:
        return ForestRegistry.deploy()
    except Exception as e:
        if _is_benign_resync_error(e):
            raise RuntimeError(
                "El deploy probablemente SI se confirmo on-chain, pero "
                "titanoboa no pudo resincronizar su estado local. Revisa "
                "en sepolia.etherscan.io la ultima tx de tu cuenta para "
                "confirmar la direccion del contrato, y continua el resto "
                "de la carga manualmente si hace falta."
            ) from e
        raise


def log_sample_tolerant(registry, name, lat_e6, lon_e6, dap_mm, hf_cm, ht_cm):
    """
    Llama a log_sample UNA vez. Si falla por el resync local post-mineo
    (la tx ya se confirmo on-chain), no reenvia -- solo lo informa y
    sigue con la proxima muestra, para no duplicar registros.
    Si el error es de otro tipo (revert real, tx no enviada, etc.),
    lo relanza porque ahi si hay que frenar y revisar.
    """
    try:
        registry.log_sample(
            name,
            lat_e6,
            lon_e6,
            dap_mm,
            hf_cm,
            ht_cm,
            DEFAULT_NDVI_E4,
            DEFAULT_SPECTRAL_SOURCE,
            field_hash(name, dap_mm, hf_cm, ht_cm),
        )
    except Exception as e:
        if _is_benign_resync_error(e):
            print(f"     (aviso: {name} probablemente SI se registro on-chain; "
                  f"solo fallo el resync local. No se reenvia.)")
            return
        raise


def deploy_forest_registry():
    registry = deploy_with_resync_tolerance()
    print(f"ForestRegistry desplegado en: {registry.address}")
    time.sleep(SECONDS_BETWEEN_TXNS)

    for i, (name, lat_e6, lon_e6, dap_mm, hf_cm, ht_cm) in enumerate(SAMPLES):
        log_sample_tolerant(registry, name, lat_e6, lon_e6, dap_mm, hf_cm, ht_cm)
        print(f"  -> muestra {i + 1}/{len(SAMPLES)} procesada: {name}")
        time.sleep(SECONDS_BETWEEN_TXNS)

    print(f"Total de muestras registradas: {registry.total_samples()}")
    return registry


def moccasin_main():
    deploy_forest_registry()