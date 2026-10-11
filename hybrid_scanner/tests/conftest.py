import pytest

from hybrid_scanner.config import DEFAULT_WATCHLIST, ScannerConfig
from hybrid_scanner.signal_generator import HybridSignalGenerator
from hybrid_scanner.utils import SyntheticProvider


@pytest.fixture(scope="session")
def universe():
    prov = SyntheticProvider()
    data = {t: prov.get_history(t) for t in DEFAULT_WATCHLIST}
    return data, prov.get_history("SPY")


@pytest.fixture(scope="session")
def cfg():
    c = ScannerConfig()
    c.output.log_level = "WARNING"
    return c


@pytest.fixture(scope="session")
def generator(cfg):
    return HybridSignalGenerator(cfg)


@pytest.fixture(scope="session")
def prepared(generator, universe):
    data, bench = universe
    return generator.prepare_universe(data, bench)
