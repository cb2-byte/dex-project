
import json
import os
from datetime import datetime
from pennyshield.base.detectors import BaseRPC, UniswapV3Monitor, create_base_risk_scorer
from pennyshield.shared.risk_engine import DetectionContext, EvidenceStore, WalletGraph

def run_health_check_with_debug():
    print("--- PennyShield Pre-Launch Health Check (Debug Mode) ---")
    
    rpc = BaseRPC()
    evidence_store = EvidenceStore(store_dir="/home/ubuntu/.openclaw/workspace/pennyshield/evidence/health_check")
    
    print("[1/4] Testing RPC Connectivity...")
    block = rpc.get_block_number()
    if block is None:
        print("❌ ERROR: Could not fetch block number. RPC unreachable.")
        return
    print(f"✅ RPC Connected. Current Block: {block}")

    print("[2/4] Testing Pool Discovery (Capturing HTTP Response)...")
    
    # Override the _request method temporarily to capture the actual response body on failure
    original_request = rpc._request
    
    def debug_request(method, params):
        import urllib.request
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        try:
            req = urllib.request.Request(rpc.rpc_url, data=payload, headers=rpc.headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if hasattr(e, 'read'):
                body = e.read().decode()
                print(f"\n--- HTTP ERROR BODY START ---\n{body}\n--- HTTP ERROR BODY END ---")
            else:
                print(f"\n--- HTTP ERROR: {e} ---")
            return None

    rpc._request = debug_request
    
    try:
        new_pools = UniswapV3Monitor(rpc, evidence_store).fetch_new_pools(block - 100, block)
        if new_pools:
            print(f"✅ Found {len(new_pools)} recent pools.")
        else:
            print("ℹ️ No new pools found in the last 100 blocks (or result was empty).")
    finally:
        rpc._request = original_request

    print("\n[3/4] Running Risk Scorer Pipeline (Verification)...")
    scorer = create_base_risk_scorer(evidence_store)
    
    pool_data = {'pool_age_hours': 2.0, 'liquidity_usd': 5000}
    token_data = {'creator': '0x1234567890123456789012345678901234567890'}
    context = DetectionContext(
        token_address="0xTestToken",
        chain="base",
        pool_data=pool_data,
        token_data=token_data,
        transactions=[],
        wallet_graph=WalletGraph(),
        metadata={'contract_analysis': {'is_contract': True, 'risks': [], 'is_proxy': False}}
    )
    
    result = scorer.score(context)
    print(f"Overall Score: {result.overall_score:.4f} (Threshold: {result.threshold})")
    for ind in result.indicator_results:
        print(f"- {ind.indicator}: Triggered={ind.triggered}, Confidence={ind.confidence:.2f}")

    print("\n[4/4] Verifying Evidence Persistence...")
    det_id = evidence_store.record_detection("0xTestToken", "base", result, pool_data, token_data)
    print(f"✅ Evidence recorded. Detection ID: {det_id}")

if __name__ == "__main__":
    run_health_check_with_debug()
