# pragma version ^0.4.1
# @license MIT
"""
@title MerkleLeaf ForestRegistry
@notice Ancla en blockchain registros biométricos y de teledetección
        (índices espectrales) de árboles muestreados en parcelas forestales.
        Cada registro queda inmutable y auditable on-chain.
"""

struct TreeSample:
    name: String[32]           # Ej: "QUEBRA 1"
    latitude_e6: int256        # grados decimales * 1e6 (negativo = Sur)
    longitude_e6: int256       # grados decimales * 1e6 (negativo = Oeste)
    dap_mm: uint256            # diámetro a la altura del pecho, en mm
    hf_cm: uint256             # altura de fuste (primera rama), en cm
    ht_cm: uint256             # altura total, en cm
    ndvi_e4: int256            # índice NDVI * 1e4 (rango real -1.0 a 1.0)
    spectral_source: String[64]  # ej: "Sentinel-2 L2A, 2026-08-10"
    data_hash: bytes32         # hash de metadata/foto/planilla de campo
    logged_by: address
    timestamp: uint256

owner: public(address)
sample_count: public(uint256)
samples: public(HashMap[uint256, TreeSample])
authorized_loggers: public(HashMap[address, bool])

event SampleLogged:
    sample_id: indexed(uint256)
    name: String[32]
    logged_by: indexed(address)
    timestamp: uint256

event LoggerAuthorized:
    logger: indexed(address)
    authorized: bool


@deploy
def __init__():
    self.owner = msg.sender
    self.authorized_loggers[msg.sender] = True


@external
def set_authorized_logger(logger: address, authorized: bool):
    """
    @notice Habilita o revoca a una dirección para cargar muestras
            (ej. el operador de campo, un oráculo de teledetección, etc.)
    """
    assert msg.sender == self.owner, "solo el owner"
    self.authorized_loggers[logger] = authorized
    log LoggerAuthorized(logger=logger, authorized=authorized)


@external
def log_sample(
    name: String[32],
    latitude_e6: int256,
    longitude_e6: int256,
    dap_mm: uint256,
    hf_cm: uint256,
    ht_cm: uint256,
    ndvi_e4: int256,
    spectral_source: String[64],
    data_hash: bytes32
) -> uint256:
    """
    @notice Registra una muestra de árbol individual con su métrica
            biométrica y su información espectral asociada.
    @return El id incremental asignado a la muestra.
    """
    assert self.authorized_loggers[msg.sender], "no autorizado"
    assert ndvi_e4 >= -10_000 and ndvi_e4 <= 10_000, "NDVI fuera de rango"

    sample_id: uint256 = self.sample_count
    self.samples[sample_id] = TreeSample(
        name=name,
        latitude_e6=latitude_e6,
        longitude_e6=longitude_e6,
        dap_mm=dap_mm,
        hf_cm=hf_cm,
        ht_cm=ht_cm,
        ndvi_e4=ndvi_e4,
        spectral_source=spectral_source,
        data_hash=data_hash,
        logged_by=msg.sender,
        timestamp=block.timestamp
    )
    self.sample_count += 1

    log SampleLogged(sample_id=sample_id, name=name, logged_by=msg.sender, timestamp=block.timestamp)
    return sample_id


@view
@external
def get_sample(sample_id: uint256) -> TreeSample:
    assert sample_id < self.sample_count, "id inexistente"
    return self.samples[sample_id]


@view
@external
def total_samples() -> uint256:
    return self.sample_count
