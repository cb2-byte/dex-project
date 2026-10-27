#!/bin/bash
cd ~/workspace/trading-bots
/usr/local/bin/python3 -W ignore coinbase_dca.py --live-test >> dca_test.log 2>&1
echo "---" >> dca_test.log
