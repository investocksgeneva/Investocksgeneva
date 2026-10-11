"""Hybrid Momentum + Swing/Pullback scanner and entry-signal generator."""

from .config import ScannerConfig
from .models import EntrySignal, ScanReport
from .signal_generator import HybridSignalGenerator

__all__ = ["ScannerConfig", "EntrySignal", "ScanReport", "HybridSignalGenerator"]
__version__ = "0.1.0"
