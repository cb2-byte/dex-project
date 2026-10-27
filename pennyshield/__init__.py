"""
PennyShield - Rug Pattern Detector
===================================
Early-warning intelligence system for detecting coordinated token extraction
and potential rug operations before buyers suffer major losses.

Supports Solana/Pump.fun and Base/Ethereum with shared intelligence.
"""

from .__main__ import PennyShield, PennyShieldConfig, create_pennyshield, quick_scan

__version__ = "0.1.0"
__author__ = "Penny"

__all__ = [
    "PennyShield",
    "PennyShieldConfig",
    "create_pennyshield",
    "quick_scan",
]