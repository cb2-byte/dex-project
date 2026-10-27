
import json
import os
from datetime import datetime
from pennyshield.base.detectors import BaseRPC, UniswapV3Monitor, create_base_risk_scorer
from pennyshield.shared.risk_engine import DetectionContext, EvidenceStore, WalletGraph

def run_health_check():
    print("--- PennyShield Pre-Launch Health Check ---")
    
    # 1. Setup
    # Using existing RPC client which has the Alchemy URL hardcoded or in config
    rpc = BaseRPC()
    evidence_store = EvidenceStore(store_dir="/home/ubuntu/.openclaw/workspace/pennyshield/evidence/health_check")
    
    # Target: Use a known active token on Base. 
    # For this test, we'll try to find a pool from the factory first to ensure connectivity.
    print("[1/4] Testing RPC Connectivity...")
    block = rpc.get_block_number()
    if block is None:
        print("❌ ERROR: Could not fetch block number. RPC unreachable.")
        return
    print(f"✅ RPC Connected. Current Block: {block}")

    # We'll use a dummy/known token address for the scan logic test
    # In a real health check, we'd use a known active rug or legitimate token.
    # For this verification, we will test the pipeline using the most recent pool.
    print("[2/4] Testing Pool Discovery...")
    new_pools = UniswapV3Monitor(rpc, evidence_store).fetch_new_pools(block - 100, block)
    if not new_pools:
        print("⚠️ No new pools in last 100 blocks. Using a known test address for pipeline verification.")
        # Mock pool data to verify the Scorer logic if no recent pools are found
        pool_data = {'pool_age_hours': 2.0, 'liquidity_usd': 5000}
        token_data = {'creator': '0x1234567890123456789012345678901234567890'}
    else:
        pool = new_pools[0]
        print(f"✅ Found recent pool: {pool['pool_address']}")
        pool_data = {'pool_age_hours': 1.0, 'liquidity_usd': 20000} # Simulated from pool
        token_data = {'creator': pool['token0']}

    # 3. Pipeline Verification
    print("[3/4] Running Risk Scorer Pipeline...")
    scorer = create_base_risk_scorer(evidence_store)
    
    # Construct a minimal context
    context = DetectionContext(
        token_address="0xTestToken",
        chain="base",
        pool_data=pool_data,
        token_data=token_data,
        transactions=[],
        wallet_graph=WalletGraph(),
        metadata={'contract_analysis': {'is_contract': True, 'risks': [], 'is_proxy': False}}
    )
    
    try:
        result = scorer.score(context)
        print("\n--- Scoring Results ---")
        print(f"Overall Score: {result.overall_score:.4f}")
        print(f"Threshold:     {result.threshold}")
        print(f"High Risk:     {result.is_high_risk}")
        print("\nComponent Scores:")
        for ind in result.indicator_results:
            print(f"- {ind.indicator}: Triggered={ind.triggered}, Confidence={ind.confidence:.2f}")
        
        # 4. Evidence Persistence
        print("\n[4/4] Verifying Evidence Persistence...")
        det_id = evidence_store.record_detection(
            "0xTestToken", "base", result, pool_data, token_data
        )
        print(f"✅ Evidence recorded. Detection ID: {det_id}")
        
    except Exception as e:
        print(f"❌ SCORER ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_health_check()
