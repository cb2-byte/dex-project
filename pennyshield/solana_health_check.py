#!/usr/bin/env python3
"""Compatibility entry point for the live-only Solana health check."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pennyshield.solana_real_health_check import run_real_solana_health_check

if __name__ == '__main__':
    sys.exit(0 if run_real_solana_health_check() else 1)
