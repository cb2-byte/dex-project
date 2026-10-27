#!/usr/bin/env python3
"""Live-only Solana discovery and evidence health check."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pennyshield.solana.detectors import SolanaRPC, PumpFunMonitor, create_solana_risk_scorer
from pennyshield.shared.risk_engine import EvidenceStore, DetectionContext, WalletGraph
from pennyshield.__main__ import PennyShieldConfig


def run_real_solana_health_check():
    print('PennyShield Solana health check (live data only)')
    rpc_url = os.environ.get('SOLANA_RPC_URL') or PennyShieldConfig().solana_rpc_url
    rpc = SolanaRPC(rpc_url)
    probe = rpc._request('getSlot', [])
    if not probe or not isinstance(probe.get('result'), int):
        print('RPC is unavailable or rate-limited; no launch data was fabricated.')
        return False
    print(f"RPC connected at slot {probe['result']}.")

    with tempfile.TemporaryDirectory(prefix='pennyshield-solana-check-') as evidence_dir:
        store = EvidenceStore(evidence_dir)
        monitor = PumpFunMonitor(rpc, store)
        launches = monitor.fetch_new_launches(limit=10)
        if not launches:
            print('No parseable real Pump.fun create was returned; health check cannot verify the pipeline.')
            return False

        launch = launches[0]
        metadata = launch.metadata or {}
        signature = metadata.get('signature')
        if not all((launch.mint, launch.creator, signature)):
            print('Discovered transaction lacked a real mint, creator, or signature.')
            return False

        token_data = {
            'creator': launch.creator,
            'name': metadata.get('name'),
            'symbol': metadata.get('symbol'),
            'metadata_uri': metadata.get('uri'),
            'funding_sources': metadata.get('funding_sources', []),
        }
        pool_data = {
            'transaction_hash': signature,
            'log_index': metadata.get('instruction_index', 0),
            'block_number': metadata.get('slot'),
            'block_time': metadata.get('block_time'),
            'bonding_curve': launch.bonding_curve,
            'discovery_source': 'pumpfun_create_instruction',
        }
        transactions = [{'signature': signature, 'slot': metadata.get('slot')}]
        context = DetectionContext(
            token_address=launch.mint,
            chain='solana',
            pool_data=pool_data,
            token_data=token_data,
            transactions=transactions,
            wallet_graph=WalletGraph(),
            historical_data={},
        )
        score = create_solana_risk_scorer(store).score(context)
        detection_id = store.record_detection(launch.mint, 'solana', score, pool_data, token_data)
        restarted_store = EvidenceStore(evidence_dir)
        replay_id = restarted_store.record_detection(launch.mint, 'solana', score, pool_data, token_data)
        record_path = os.path.join(evidence_dir, f'{detection_id}.json')
        with open(record_path) as handle:
            record = json.load(handle)
        graph = restarted_store.get_operator_graph(f'deployer:{launch.creator}', depth=2)

        if replay_id != detection_id or record.get('pool_snapshot', {}).get('transaction_hash') != signature:
            print('Evidence identity or transaction-signature persistence check failed.')
            return False
        if not any(edge.get('relationship') == 'deployed' for edge in graph.get('edges', [])):
            print('Creator-to-launch graph edge was not persisted.')
            return False

        print('Verified real launch evidence:')
        print(f'  Mint: {launch.mint}')
        print(f'  Creator: {launch.creator}')
        print(f'  Signature: {signature}')
        print(f'  Slot: {metadata.get("slot")}')
        print(f'  Score: {score.overall_score:.4f} (threshold {score.threshold:.2f})')
        print(f'  Stable evidence ID across reload: {detection_id}')
        print('  Creator → launch graph edge: persisted')
        return True


if __name__ == '__main__':
    sys.exit(0 if run_real_solana_health_check() else 1)
