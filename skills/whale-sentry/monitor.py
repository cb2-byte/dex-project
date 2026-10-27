#!/usr/bin/env python3
"""
Whale Sentry Continuous Monitor
Runs 24/7 checking whale wallets for large transfers
"""
import os
import sys
import time
import signal
import logging
from pathlib import Path

# Add skill to path
skill_dir = Path(__file__).parent
sys.path.insert(0, str(skill_dir))

# Import using absolute imports
from whale_sentry import WhaleSentry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(skill_dir / 'monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global for graceful shutdown
monitor = None
shutdown = False

def signal_handler(sig, frame):
    global shutdown
    logger.info("Shutdown signal received...")
    shutdown = True
    if monitor:
        monitor.stop_monitoring()

def main():
    global monitor, shutdown
    
    # Load env
    from dotenv import load_dotenv
    load_dotenv(skill_dir / '.env')
    
    # Initialize
    monitor = WhaleSentry()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 50)
    logger.info("Whale Sentry Monitor Starting")
    logger.info("=" * 50)
    
    # List configured wallets
    wallets = monitor.list_wallets()
    logger.info(f"Monitoring {len(wallets)} wallets:")
    for w in wallets:
        logger.info(f"  - {w['label']} ({w['chain']}): {w['address'][:10]}...")
    
    # Start monitoring
    logger.info("Starting continuous monitoring loop (60s interval)...")
    monitor.start_monitoring(interval_seconds=60)
    
    # Keep alive
    try:
        while not shutdown:
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Stopping monitor...")
        monitor.stop_monitoring()
        logger.info("Whale Sentry Monitor Stopped")

if __name__ == "__main__":
    main()