"""
PennyShield Main Integration Layer
===================================
Coordinates all detection modules, evidence store, alerts, and replay.
Main entry point for running PennyShield monitoring.
"""
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
import os

from .shared.risk_engine import (
    RiskScorer, RiskScore, DetectionContext, EvidenceStore, WalletGraph
)
from .solana.detectors import create_solana_risk_scorer, SolanaRPC, PumpFunMonitor
from .base.detectors import create_base_risk_scorer, BaseRPC, UniswapV3Monitor, ContractPermissionAnalyzer
from .shared.social_intel import (
    create_social_risk_scorer, SocialDataCollector, CombinedRiskAssessor,
    SocialMention
)
from .alerts.telegram_alerts import (
    AlertProcessor, AlertManager, TelegramDelivery, TelegramFormatter
)
from .replay.validation import HistoricalReplay, ScenarioTester


def _configured_rpc_url(network: str, public_fallback: str) -> str:
    """Build an Alchemy URL from a secret environment variable, if present."""
    explicit_url = os.environ.get(f'{network.upper().replace("-", "_")}_RPC_URL')
    if explicit_url:
        return explicit_url
    api_key = os.environ.get('ALCHEMY_API_KEY')
    if api_key:
        return f'https://{network}.g.alchemy.com/v2/{api_key}'
    return public_fallback


# === Configuration ===
@dataclass
class PennyShieldConfig:
    """Configuration for PennyShield"""
    # Data sources
    solana_rpc_url: str = field(default_factory=lambda: _configured_rpc_url(
        'solana-mainnet', 'https://api.mainnet-beta.solana.com'))
    base_rpc_url: str = field(default_factory=lambda: _configured_rpc_url(
        'base-mainnet', 'https://mainnet.base.org'))
    
    # Monitoring
    scan_interval_seconds: int = 300  # 5 minutes
    new_pool_scan_blocks: int = 100
    
    # Alerts
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    # Thresholds
    high_risk_threshold: float = 0.65
    
    # Storage
    evidence_dir: str = "/home/ubuntu/.openclaw/workspace/pennyshield/evidence"
    alerts_dir: str = "/home/ubuntu/.openclaw/workspace/pennyshield/alerts"
    replay_dir: str = "/home/ubuntu/.openclaw/workspace/pennyshield/replay"
    
    # Social data (mock for now)
    use_mock_social: bool = True


# === PennyShield Core ===
class PennyShield:
    """Main PennyShield orchestrator"""
    
    def __init__(self, config: PennyShieldConfig = None):
        self.config = config or PennyShieldConfig()
        self.running = False
        self.scan_thread: Optional[threading.Thread] = None
        self.last_base_scanned_block: Optional[int] = None
        
        # Initialize components
        self._init_components()
        
        # Statistics
        self.stats = {
            'scans_completed': 0,
            'tokens_analyzed': 0,
            'alerts_generated': 0,
            'high_risk_detected': 0,
            'errors': 0,
            'start_time': time.time()
        }
    
    def _init_components(self):
        """Initialize all PennyShield components"""
        # Evidence store (persistent memory)
        self.evidence_store = EvidenceStore(self.config.evidence_dir)
        
        # Risk scorers
        self.solana_scorer = create_solana_risk_scorer(self.evidence_store)
        self.base_scorer = create_base_risk_scorer(self.evidence_store)
        self.social_scorer = create_social_risk_scorer(self.evidence_store)
        self.combined_assessor = CombinedRiskAssessor(self.solana_scorer, self.social_scorer)
        
        # RPC clients
        self.solana_rpc = SolanaRPC(self.config.solana_rpc_url)
        self.base_rpc = BaseRPC(self.config.base_rpc_url)
        
        # Monitors
        self.pumpfun_monitor = PumpFunMonitor(self.solana_rpc, self.evidence_store)
        self.uniswap_monitor = UniswapV3Monitor(self.base_rpc, self.evidence_store)
        self.contract_analyzer = ContractPermissionAnalyzer(self.base_rpc)
        
        # Social data
        self.social_collector = SocialDataCollector()
        
        # Alerts
        delivery = TelegramDelivery(self.config.telegram_bot_token, self.config.telegram_chat_id)
        self.alert_processor = AlertProcessor(self.evidence_store, delivery)
        
        # Replay/Validation
        self.replay = HistoricalReplay(self.evidence_store, self.solana_scorer, self.base_scorer)
        self.scenario_tester = ScenarioTester(self.replay)
        
        # Known tokens tracking
        self.known_tokens: Dict[str, Dict] = {}  # token_address -> last scan data
    
    def scan_token(self, token_address: str, chain: str,
                   token_symbol: str = None, token_name: str = None,
                   pool_data: Dict = None, token_data: Dict = None,
                   transactions: List[Dict] = None,
                   wallet_graph: WalletGraph = None,
                   social_data: Dict = None) -> Optional[Dict]:
        """Scan a single token for rug patterns"""
        try:
            # Build detection context
            context = self._build_context(
                token_address, chain, token_symbol, token_name,
                pool_data, token_data, transactions, wallet_graph, social_data
            )
            
            # Run appropriate risk assessment
            if chain == 'solana':
                risk_score = self.solana_scorer.score(context)
            elif chain in ('base', 'ethereum'):
                risk_score = self.base_scorer.score(context)
            else:
                risk_score = RiskScore(
                    overall_score=0.0, threshold=0.0, is_high_risk=False,
                    indicator_results=[], triggered_indicators=[], timestamp=time.time()
                )
            
            # Also run social assessment if data available
            combined_result = None
            if social_data:
                combined_result = self.combined_assessor.assess(context)
                # Use combined score for alerting
                final_score = combined_result['combined_score']
                is_high_risk = combined_result['is_high_risk']
                triggered = list(set(
                    risk_score.triggered_indicators + 
                    combined_result.get('social_indicators', [])
                ))
            else:
                final_score = risk_score.overall_score
                is_high_risk = risk_score.is_high_risk
                triggered = risk_score.triggered_indicators
            
            # Update stats
            self.stats['tokens_analyzed'] += 1
            if is_high_risk:
                self.stats['high_risk_detected'] += 1
            
            # Process alert if high risk
            alert = None
            if is_high_risk and final_score >= self.config.high_risk_threshold:
                alert = self.alert_processor.process_risk_score(
                    token_address=token_address,
                    chain=chain,
                    token_symbol=token_symbol or 'UNKNOWN',
                    token_name=token_name or 'Unknown',
                    risk_score=risk_score,
                    pool_data=pool_data or {},
                    token_data=token_data or {},
                    transaction_links=self._extract_tx_links(transactions or [])
                )
                if alert:
                    self.stats['alerts_generated'] += 1
            
            # Store scan result
            scan_result = {
                'token_address': token_address,
                'chain': chain,
                'token_symbol': token_symbol,
                'token_name': token_name,
                'risk_score': final_score,
                'is_high_risk': is_high_risk,
                'triggered_indicators': triggered,
                'onchain_indicators': risk_score.triggered_indicators,
                'social_indicators': combined_result.get('social_indicators', []) if combined_result else [],
                'agreement': combined_result.get('agreement') if combined_result else None,
                'alert_id': alert.alert_id if alert else None,
                'timestamp': time.time(),
                'pool_data': pool_data,
                'token_data': token_data
            }
            
            self.known_tokens[token_address] = scan_result
            
            # Record in evidence store
            self.evidence_store.record_detection(
                token_address, chain, risk_score, pool_data or {}, token_data or {}
            )
            
            return scan_result
            
        except Exception as e:
            self.stats['errors'] += 1
            print(f"[ERROR] Scan failed for {token_address}: {e}")
            return None
    
    def _build_context(self, token_address: str, chain: str,
                       token_symbol: str, token_name: str,
                       pool_data: Dict, token_data: Dict,
                       transactions: List[Dict], wallet_graph: WalletGraph,
                       social_data: Dict) -> DetectionContext:
        """Build detection context from available data"""
        
        # Build wallet graph if not provided
        if wallet_graph is None:
            wallet_graph = WalletGraph()
            holders = token_data.get('holders', []) if token_data else []
            for holder in holders:
                addr = holder.get('address')
                if addr:
                    node = wallet_graph.add_wallet(addr)
                    node.tokens_held[token_address] = holder.get('amount', 0)
        
        # Extract on-chain metrics
        onchain_metrics = {}
        if token_data:
            onchain_metrics = {
                'unique_buyers_24h': token_data.get('unique_buyers_24h', 0),
                'net_buy_volume_usd_24h': token_data.get('net_buy_volume_usd_24h', 0),
                'top_10_holder_pct': token_data.get('top_10_holder_pct', 0),
            }
        
        return DetectionContext(
            token_address=token_address,
            chain=chain,
            pool_data=pool_data or {},
            token_data=token_data or {},
            transactions=transactions or [],
            wallet_graph=wallet_graph,
            historical_data={},
            metadata={
                'social_data': social_data or {},
                'onchain_metrics': onchain_metrics
            }
        )
    
    def _extract_tx_links(self, transactions: List[Dict]) -> List[str]:
        """Extract transaction explorer links"""
        links = []
        for tx in transactions[:10]:
            tx_hash = tx.get('hash') or tx.get('transaction_hash') or tx.get('signature')
            if tx_hash:
                if tx_hash.startswith('0x'):
                    links.append(f"https://basescan.org/tx/{tx_hash}")
                else:
                    links.append(f"https://solscan.io/tx/{tx_hash}")
        return links
    
    def scan_new_launches(self) -> List[Dict]:
        """Scan for new token launches on both chains"""
        results = []
        
        # Scan Solana/Pump.fun new launches
        try:
            solana_results = self._scan_solana_new_launches()
            results.extend(solana_results)
        except Exception as e:
            print(f"[WARNING] Solana new launch scan failed: {e}")
            self.stats['errors'] += 1
        
        # Scan Base/Ethereum new pools
        try:
            base_results = self._scan_base_new_pools()
            results.extend(base_results)
        except Exception as e:
            print(f"[WARNING] Base new pool scan failed: {e}")
            self.stats['errors'] += 1
        
        self.stats['scans_completed'] += 1
        return results
    
    def _scan_solana_new_launches(self) -> List[Dict]:
        """Discover and score new Pump.fun launches from on-chain transactions."""
        launches = self.pumpfun_monitor.fetch_new_launches(limit=50)
        results = []
        for launch in launches:
            metadata = launch.metadata or {}
            signature = metadata.get('signature')
            if not signature or not launch.mint or not launch.creator:
                continue

            pool_data = {
                'transaction_hash': signature,
                'log_index': metadata.get('instruction_index', 0),
                'block_number': metadata.get('slot'),
                'block_time': metadata.get('block_time'),
                'bonding_curve': launch.bonding_curve,
                'associated_bonding_curve': launch.associated_bonding_curve,
                'real_sol_reserves': launch.real_sol_reserves,
                'virtual_sol_reserves': launch.virtual_sol_reserves,
                'virtual_token_reserves': launch.virtual_token_reserves,
                'discovery_source': 'pumpfun_create_instruction',
            }
            token_data = {
                'creator': launch.creator,
                'name': metadata.get('name'),
                'symbol': metadata.get('symbol'),
                'metadata_uri': metadata.get('uri'),
                'launch_timestamp': launch.created_timestamp,
                'launch_slot': metadata.get('slot'),
                'instruction': metadata.get('instruction'),
                'funding_sources': metadata.get('funding_sources', []),
            }
            result = self.scan_token(
                token_address=launch.mint,
                chain='solana',
                token_symbol=metadata.get('symbol') or 'NEW',
                token_name=metadata.get('name') or 'New Pump.fun token',
                pool_data=pool_data,
                token_data=token_data,
                transactions=[{'signature': signature, 'slot': metadata.get('slot')}],
            )
            if result:
                results.append(result)
        return results

    def _scan_base_new_pools(self) -> List[Dict]:
        """Scan for new Uniswap V3 pools on Base"""
        current_block = self.base_rpc.get_block_number()
        if not current_block:
            return []
        
        from_block = max(0, current_block - self.config.new_pool_scan_blocks)
        if self.last_base_scanned_block is not None:
            from_block = max(from_block, self.last_base_scanned_block + 1)
        new_pools = self.uniswap_monitor.fetch_new_pools(from_block, current_block)
        
        results = []
        for pool in new_pools:
            # Get token data for token0 (usually the new token)
            token_address = pool['token0']
            
            # Analyze contract
            contract_analysis = self.contract_analyzer.analyze_contract(token_address)
            
            # Basic pool data
            pool_data = {
                'pool_address': pool['pool_address'],
                'token0': pool['token0'],
                'token1': pool['token1'],
                'fee': pool['fee'],
                'pool_age_hours': 0,
                'liquidity_usd': 0  # Would need to fetch
            }
            
            token_data = {
                'creator': pool.get('creator', ''),
                'contract_analysis': contract_analysis
            }
            
            # Scan the token
            result = self.scan_token(
                token_address=token_address,
                chain='base',
                token_symbol=token_data.get('symbol', 'NEW'),
                token_name=token_data.get('name', 'New Token'),
                pool_data=pool_data,
                token_data=token_data
            )
            
            if result:
                results.append(result)

        self.last_base_scanned_block = current_block
        return results
    
    def scan_monitored_tokens(self, token_addresses: List[str], chain: str) -> List[Dict]:
        """Scan a list of previously discovered tokens"""
        results = []
        
        for token_address in token_addresses:
            # Would fetch current data from APIs
            # For now, use last known data
            if token_address in self.known_tokens:
                last_data = self.known_tokens[token_address]
                result = self.scan_token(
                    token_address=token_address,
                    chain=chain,
                    token_symbol=last_data.get('token_symbol'),
                    token_name=last_data.get('token_name'),
                    pool_data=last_data.get('pool_data'),
                    token_data=last_data.get('token_data')
                )
                if result:
                    results.append(result)
        
        return results
    
    def start_monitoring(self, token_addresses: List[str] = None, 
                         chains: List[str] = None):
        """Start continuous monitoring"""
        if self.running:
            print("[INFO] Already monitoring")
            return
        
        self.running = True
        self.token_addresses = token_addresses or []
        self.chains = chains or ['solana', 'base']
        
        self.scan_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.scan_thread.start()
        print(f"[INFO] PennyShield monitoring started (interval: {self.config.scan_interval_seconds}s)")
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5)
        print("[INFO] PennyShield monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Scan new launches
                new_results = self.scan_new_launches()
                print(f"[INFO] Scanned new launches: {len(new_results)} tokens analyzed")
                
                # Scan monitored tokens
                if self.token_addresses:
                    for chain in self.chains:
                        chain_tokens = [t for t in self.token_addresses if self._get_chain(t) == chain]
                        if chain_tokens:
                            self.scan_monitored_tokens(chain_tokens, chain)
                
                # Print stats periodically
                if self.stats['scans_completed'] % 10 == 0:
                    self._print_stats()
                
            except Exception as e:
                print(f"[ERROR] Monitor loop error: {e}")
                self.stats['errors'] += 1
            
            time.sleep(self.config.scan_interval_seconds)
    
    def _get_chain(self, token_address: str) -> str:
        """Guess chain from token address format"""
        if token_address.startswith('0x'):
            return 'base'
        return 'solana'
    
    def _print_stats(self):
        """Print monitoring statistics"""
        elapsed = time.time() - self.stats['start_time']
        print(f"\n{'='*50}")
        print(f"PENNYSHIELD STATS (running {elapsed/60:.1f} min)")
        print(f"{'='*50}")
        print(f"Scans completed:     {self.stats['scans_completed']}")
        print(f"Tokens analyzed:     {self.stats['tokens_analyzed']}")
        print(f"High risk detected:  {self.stats['high_risk_detected']}")
        print(f"Alerts generated:    {self.stats['alerts_generated']}")
        print(f"Errors:              {self.stats['errors']}")
        print(f"{'='*50}\n")
    
    def run_validation(self) -> Dict[str, Any]:
        """Run historical validation"""
        print("[INFO] Running historical validation...")
        metrics = self.replay.run_replay()
        self.replay.print_summary()
        self.replay.save_results()
        return self.replay.get_metrics_summary()
    
    def run_scenarios(self) -> List[Dict]:
        """Run built-in test scenarios"""
        print("[INFO] Running test scenarios...")
        results = self.scenario_tester.run_all_scenarios()
        for r in results:
            lead = r.lead_time_hours if r.lead_time_hours is not None else 0.0
            print(f"  {r.token.token_symbol}: score={r.risk_score.overall_score:.1%}, "
                  f"TP={r.is_true_positive}, FP={r.is_false_positive}, "
                  f"FN={r.is_false_negative}, lead={lead:.1f}h")
        return [
            {
                'token': r.token.token_symbol,
                'outcome': r.token.outcome,
                'risk_score': r.risk_score.overall_score,
                'is_true_positive': r.is_true_positive,
                'is_false_positive': r.is_false_positive,
                'is_false_negative': r.is_false_negative,
                'lead_time_hours': r.lead_time_hours
            }
            for r in results
        ]
    
    def get_active_alerts(self, chain: str = None, min_severity: str = 'medium') -> List[Dict]:
        """Get active alerts"""
        alerts = self.alert_processor.alert_manager.get_active_alerts(chain, min_severity)
        return [a.to_dict() for a in alerts]
    
    def get_alert_summary(self, chain: str = None) -> str:
        """Get formatted alert summary"""
        return self.alert_processor.get_alert_summary(chain)
    
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert"""
        self.alert_processor.alert_manager.acknowledge_alert(alert_id)
    
    def set_alert_outcome(self, alert_id: str, outcome: str, details: Dict = None):
        """Set alert outcome for learning"""
        self.alert_processor.alert_manager.set_outcome(alert_id, outcome, details)
        # Also record in evidence store for operator linking
        if outcome == 'rug':
            # Would link to deployer/wallet clusters
            pass
    
    def export_evidence_base(self, path: str = None) -> str:
        """Export evidence base for analysis"""
        path = path or "/home/ubuntu/.openclaw/workspace/pennyshield/evidence_base.json"
        
        export_data = {
            'evidence_store_index': self.evidence_store.index,
            'statistics': self.evidence_store.get_statistics(),
            'alerts': [a.to_dict() for a in self.alert_processor.alert_manager.alert_history],
            'known_tokens': self.known_tokens,
            'stats': self.stats,
            'export_timestamp': time.time(),
            'export_timestamp_iso': datetime.now().isoformat()
        }
        
        with open(path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"[INFO] Evidence base exported to {path}")
        return path


# === Convenience Functions ===
def create_pennyshield(config: PennyShieldConfig = None) -> PennyShield:
    """Create a PennyShield instance"""
    return PennyShield(config)


def quick_scan(token_address: str, chain: str, 
               token_symbol: str = None, token_name: str = None) -> Dict:
    """Quick one-off scan without full monitoring setup"""
    shield = PennyShield()
    return shield.scan_token(token_address, chain, token_symbol, token_name)


# === Example Usage ===
if __name__ == "__main__":
    # Example: Create and test PennyShield
    config = PennyShieldConfig(
        scan_interval_seconds=60,  # 1 minute for testing
        use_mock_social=True
    )
    
    shield = PennyShield(config)
    
    # Run test scenarios
    print("Running PennyShield test scenarios...")
    scenario_results = shield.run_scenarios()
    
    # Run validation if historical data exists
    # shield.run_validation()
    
    # Example scan
    # result = shield.scan_token(
    #     token_address="0x...",
    #     chain="base",
    #     token_symbol="TEST",
    #     token_name="Test Token",
    #     pool_data={'liquidity_usd': 50000},
    #     token_data={'creator': '0x...', 'total_supply': 1_000_000_000}
    # )
    # print(f"Scan result: {result}")
    
    print("\nPennyShield initialized and ready.")
    print("Use shield.start_monitoring() to begin continuous monitoring.")
    print("Use shield.scan_token() for individual token analysis.")
    print("Use shield.run_validation() to validate against historical data.")
