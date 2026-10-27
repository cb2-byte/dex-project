"""Systemd entry point for PennyShield's continuous read-only observer."""
import os
import signal
import sys
import threading

from pennyshield.__main__ import PennyShield, PennyShieldConfig


def main() -> int:
    if not os.environ.get('ALCHEMY_API_KEY') and not (
        os.environ.get('SOLANA_MAINNET_RPC_URL') and os.environ.get('BASE_MAINNET_RPC_URL')
    ):
        raise RuntimeError(
            'Set ALCHEMY_API_KEY or both chain RPC URLs in the observer environment file.'
        )

    observer = PennyShield(PennyShieldConfig())
    shutdown = threading.Event()

    def stop_observer(_signum, _frame):
        if not shutdown.is_set():
            shutdown.set()
            observer.stop_monitoring()

    signal.signal(signal.SIGTERM, stop_observer)
    signal.signal(signal.SIGINT, stop_observer)
    observer.start_monitoring()
    try:
        shutdown.wait()
    finally:
        if not shutdown.is_set():
            observer.stop_monitoring()
    return 0


if __name__ == '__main__':
    sys.exit(main())
