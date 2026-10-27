
import hashlib
import time
from typing import Dict, Any
from pennyshield.shared.risk_engine import EvidenceStore, RiskScore, RiskIndicator

def mock_risk_score(overall_score=0.1, threshold=0.65):
    # Mocking a RiskScore object since it's a dataclass
    class MockScore:
        def __init__(self):
            self.overall_score = overall_score
            self.threshold = threshold
            self.is_high_risk = overall_score >= threshold
            self.indicator_results = []
            self.triggered_indicators = []
            self.timestamp = time.time()
        def to_dict(self):
            return {"overall_score": self.overall_score}
    return MockScore()

def test_deterministic_ids():
    print("--- Testing Deterministic Detection IDs ---")
    store = EvidenceStore(store_dir="/home/ubuntu/.openclaw/workspace/pennyshield/evidence/test_ids")
    
    # Scenario 1: Same event scanned twice (Preferred path)
    pool_data_1 = {
        'transaction_hash': '0xabc123',
        'log_index': 10,
        'block_number': 1000
    }
    token_data = {'creator': '0xdeployer'}
    score = mock_risk_score()
    
    id1 = store.record_detection("0xTokenA", "base", score, pool_data_1, token_data)
    id2 = store.record_detection("0xTokenA", "base", score, pool_data_1, token_data)
    
    print(f"Test 1 (Stability): {'✅' if id1 == id2 else '❌'} (ID1: {id1}, ID2: {id2})")

    # Scenario 2: Two different events in the same block (Preferred path)
    pool_data_2 = {
        'transaction_hash': '0xdef456',
        'log_index': 20,
        'block_number': 1000
    }
    id3 = store.record_detection("0xTokenB", "base", score, pool_data_2, token_data)
    print(f"Test 2 (Uniqueness): {'✅' if id1 != id3 else '❌'} (ID1: {id1}, ID3: {id3})")

    # Scenario 3: Missing tx_hash/log_index (Fallback path)
    pool_data_fallback = {
        'block_number': 1000
    }
    id4 = store.record_detection("0xTokenC", "base", score, pool_data_fallback, token_data)
    print(f"Test 3 (Fallback): {'✅' if id4 else '❌'} (ID: {id4})")

    # Scenario 4: Missing all metadata (Unstable path)
    pool_data_empty = {}
    id5 = store.record_detection("0xTokenD", "base", score, pool_data_empty, token_data)
    print(f"Test 4 (Unstable): {'✅' if id5 else '❌'} (ID: {id5})")
    
    # Check if the unstable flag was actually written to the file
    import json
    import os
    with open(os.path.join(store.store_dir, f"{id5}.json"), 'r') as f:
        record = json.load(f)
        status = record.get('metadata', {}).get('deduplication_status')
        print(f"Test 5 (Unstable Flag): {'✅' if status == 'unstable' else '❌'} (Status: {status})")

if __name__ == "__main__":
    test_deterministic_ids()
