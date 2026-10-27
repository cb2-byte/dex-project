"""
Historical Replay & Validation Framework
=========================================
Replays historical rugs and legitimate launches to measure
detection lead time, false positives, and missed attacks.
"""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import os

from ..shared.risk_engine import RiskScorer, RiskScore, DetectionContext, EvidenceStore
from ..solana.detectors import create_solana_risk_scorer
from ..base.detectors import create_base_risk_scorer


# === Replay Data Structures ===
@dataclass
class HistoricalToken:
    """A token from historical data for replay"""
    token_address: str
    chain: str
    token_symbol: str
    token_name: str
    launch_timestamp: float
    outcome: str  # 'rug', 'legitimate', 'unknown'
    outcome_timestamp: Optional[float] = None
    outcome_details: Dict = field(default_factory=dict)
    pool_data: Dict = field(default_factory=dict)
    token_data: Dict = field(default_factory=dict)
    transactions: List[Dict] = field(default_factory=list)
    social_data: Dict = field(default_factory=dict)
    wallet_graph: Dict = field(default_factory=dict)


@dataclass
class ReplayResult:
    """Result of replaying detection on a historical token"""
    token: HistoricalToken
    risk_score: RiskScore
    detection_timestamp: float
    lead_time_hours: Optional[float] = None  # Hours before outcome
    is_true_positive: bool = False
    is_false_positive: bool = False
    is_true_negative: bool = False
    is_false_negative: bool = False
    triggered_indicators: List[str] = field(default_factory=list)
    missed_indicators: List[str] = field(default_factory=list)


@dataclass
class ValidationMetrics:
    """Aggregated validation metrics"""
    total_tokens: int = 0
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    avg_lead_time_hours: float = 0.0
    lead_times: List[float] = field(default_factory=list)
    by_chain: Dict[str, Dict] = field(default_factory=dict)
    by_indicator: Dict[str, Dict] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# === Replay Engine ===
class HistoricalReplay:
    """Replay detection on historical data for validation"""
    
    def __init__(self, 
                 evidence_store: EvidenceStore,
                 solana_scorer: RiskScorer = None,
                 base_scorer: RiskScorer = None):
        self.evidence_store = evidence_store
        self.solana_scorer = solana_scorer or create_solana_risk_scorer(evidence_store)
        self.base_scorer = base_scorer or create_base_risk_scorer(evidence_store)
        self.replay_results: List[ReplayResult] = []
        self.metrics: ValidationMetrics = ValidationMetrics()
        self.historical_tokens: List[HistoricalToken] = []
    
    def load_historical_tokens(self, data_dir: str) -> List[HistoricalToken]:
        """Load historical tokens from data directory"""
        tokens = []
        
        # Load from evidence store
        for token_addr, detections in self.evidence_store.index.get('tokens', {}).items():
            for det_id in detections:
                detail_path = os.path.join(self.evidence_store.store_dir, f"{det_id}.json")
                if os.path.exists(detail_path):
                    with open(detail_path, 'r') as f:
                        record = json.load(f)
                    
                    token = HistoricalToken(
                        token_address=record.get('token_address', token_addr),
                        chain=record.get('chain', 'unknown'),
                        token_symbol=record.get('token_snapshot', {}).get('symbol', 'UNKNOWN'),
                        token_name=record.get('token_snapshot', {}).get('name', 'Unknown'),
                        launch_timestamp=record.get('timestamp', 0),
                        outcome=record.get('outcome', 'unknown'),
                        outcome_timestamp=record.get('outcome_timestamp'),
                        outcome_details=record.get('outcome_details', {}),
                        pool_data=record.get('pool_snapshot', {}),
                        token_data=record.get('token_snapshot', {}),
                    )
                    tokens.append(token)
        
        return tokens
    
    def add_historical_token(self, token: HistoricalToken):
        """Add a historical token for replay"""
        self.historical_tokens.append(token)
    
    def run_replay(self, tokens: List[HistoricalToken] = None) -> ValidationMetrics:
        """Run replay on historical tokens"""
        tokens = tokens or self.historical_tokens
        self.replay_results = []
        
        for token in tokens:
            result = self._replay_token(token)
            self.replay_results.append(result)
        
        self._calculate_metrics()
        return self.metrics
    
    def _replay_token(self, token: HistoricalToken) -> ReplayResult:
        """Replay detection on a single historical token"""
        # Build detection context
        context = self._build_context(token)
        
        # Run appropriate scorer
        if token.chain == 'solana':
            risk_score = self.solana_scorer.score(context)
        elif token.chain in ('base', 'ethereum'):
            risk_score = self.base_scorer.score(context)
        else:
            risk_score = RiskScore(
                overall_score=0.0, threshold=0.0, is_high_risk=False,
                indicator_results=[], triggered_indicators=[], timestamp=time.time()
            )
        
        # Calculate lead time
        lead_time = None
        if token.outcome_timestamp and token.outcome == 'rug':
            lead_time = (token.outcome_timestamp - risk_score.timestamp) / 3600
        
        # Classify result
        is_high_risk = risk_score.is_high_risk
        is_rug = token.outcome == 'rug'
        
        if is_high_risk and is_rug:
            tp, fp, tn, fn = True, False, False, False
        elif is_high_risk and not is_rug:
            tp, fp, tn, fn = False, True, False, False
        elif not is_high_risk and is_rug:
            tp, fp, tn, fn = False, False, False, True
        else:
            tp, fp, tn, fn = False, False, True, False
        
        return ReplayResult(
            token=token,
            risk_score=risk_score,
            detection_timestamp=risk_score.timestamp,
            lead_time_hours=lead_time,
            is_true_positive=tp,
            is_false_positive=fp,
            is_true_negative=tn,
            is_false_negative=fn,
            triggered_indicators=risk_score.triggered_indicators
        )
    
    def _build_context(self, token: HistoricalToken) -> DetectionContext:
        """Build detection context from historical token"""
        # Build wallet graph
        wallet_graph = self._build_wallet_graph(token)
        
        # Build historical_data with pool liquidity history for detectors
        # LiquidityDrainDetector (Base) and ExitDetector (Solana) expect
        # previous_liquidity_usd in historical_data
        historical_data = dict(token.outcome_details) if token.outcome_details else {}
        pool_data = token.pool_data or {}
        if 'previous_liquidity_usd' in pool_data:
            historical_data['previous_liquidity_usd'] = pool_data['previous_liquidity_usd']
        
        return DetectionContext(
            token_address=token.token_address,
            chain=token.chain,
            pool_data=pool_data,
            token_data=token.token_data,
            transactions=token.transactions,
            wallet_graph=wallet_graph,
            historical_data=historical_data,
            metadata={
                'social_data': token.social_data,
                'onchain_metrics': self._extract_onchain_metrics(token)
            }
        )
    
    def _build_wallet_graph(self, token: HistoricalToken) -> 'WalletGraph':
        """Build wallet graph from historical data"""
        from pennyshield.shared.risk_engine import WalletGraph
        
        graph = WalletGraph()
        
        # Add wallets from token data
        holders = token.token_data.get('holders', [])
        for holder in holders:
            addr = holder.get('address')
            if addr:
                node = graph.add_wallet(addr)
                node.tokens_held[token.token_address] = holder.get('amount', 0)
        
        # Add edges from wallet graph data
        # Also ensure all addresses in edges are added as nodes (not just holders)
        for edge_data in token.wallet_graph.get('edges', []):
            from_addr = edge_data.get('from')
            to_addr = edge_data.get('to')
            edge_type = edge_data.get('type', 'unknown')
            
            # Ensure both addresses exist as nodes
            if from_addr and from_addr not in graph.nodes:
                graph.add_wallet(from_addr)
            if to_addr and to_addr not in graph.nodes:
                graph.add_wallet(to_addr)
            
            graph.add_edge(
                from_addr,
                to_addr,
                edge_type,
                weight=edge_data.get('weight', 1.0),
                evidence=edge_data.get('evidence', {}),
                timestamp=edge_data.get('timestamp', 0)
            )
            
            # Also update node attributes for funded/funded_wallets
            if edge_type == 'funded':
                from_node = graph.nodes.get(from_addr)
                to_node = graph.nodes.get(to_addr)
                if from_node and to_node:
                    if to_addr not in from_node.funded_wallets:
                        from_node.funded_wallets.append(to_addr)
                    if from_addr not in to_node.funding_sources:
                        to_node.funding_sources.append(from_addr)
        
        return graph
    
    def _extract_onchain_metrics(self, token: HistoricalToken) -> Dict:
        """Extract on-chain metrics from historical data"""
        return {
            'unique_buyers_24h': token.token_data.get('unique_buyers_24h', 0),
            'net_buy_volume_usd_24h': token.token_data.get('net_buy_volume_usd_24h', 0),
            'top_10_holder_pct': token.token_data.get('top_10_holder_pct', 0),
        }
    
    def _calculate_metrics(self):
        """Calculate aggregated validation metrics"""
        if not self.replay_results:
            return
        
        self.metrics.total_tokens = len(self.replay_results)
        self.metrics.true_positives = sum(1 for r in self.replay_results if r.is_true_positive)
        self.metrics.false_positives = sum(1 for r in self.replay_results if r.is_false_positive)
        self.metrics.true_negatives = sum(1 for r in self.replay_results if r.is_true_negative)
        self.metrics.false_negatives = sum(1 for r in self.replay_results if r.is_false_negative)
        
        # Precision, recall, F1
        tp = self.metrics.true_positives
        fp = self.metrics.false_positives
        fn = self.metrics.false_negatives
        
        self.metrics.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        self.metrics.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        self.metrics.f1_score = (2 * self.metrics.precision * self.metrics.recall / 
                                 (self.metrics.precision + self.metrics.recall) 
                                 if (self.metrics.precision + self.metrics.recall) > 0 else 0.0)
        
        # Lead times
        lead_times = [r.lead_time_hours for r in self.replay_results 
                      if r.lead_time_hours is not None and r.is_true_positive]
        self.metrics.lead_times = lead_times
        self.metrics.avg_lead_time_hours = sum(lead_times) / len(lead_times) if lead_times else 0.0
        
        # By chain
        for result in self.replay_results:
            chain = result.token.chain
            if chain not in self.metrics.by_chain:
                self.metrics.by_chain[chain] = {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0, 'total': 0}
            
            self.metrics.by_chain[chain]['total'] += 1
            if result.is_true_positive:
                self.metrics.by_chain[chain]['tp'] += 1
            elif result.is_false_positive:
                self.metrics.by_chain[chain]['fp'] += 1
            elif result.is_true_negative:
                self.metrics.by_chain[chain]['tn'] += 1
            elif result.is_false_negative:
                self.metrics.by_chain[chain]['fn'] += 1
        
        # By indicator
        for result in self.replay_results:
            for ind in result.triggered_indicators:
                if ind not in self.metrics.by_indicator:
                    self.metrics.by_indicator[ind] = {'triggered': 0, 'tp': 0, 'fp': 0}
                self.metrics.by_indicator[ind]['triggered'] += 1
                if result.is_true_positive:
                    self.metrics.by_indicator[ind]['tp'] += 1
                elif result.is_false_positive:
                    self.metrics.by_indicator[ind]['fp'] += 1
        
        self.metrics.timestamp = time.time()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics as dictionary"""
        return {
            'total_tokens': self.metrics.total_tokens,
            'true_positives': self.metrics.true_positives,
            'false_positives': self.metrics.false_positives,
            'true_negatives': self.metrics.true_negatives,
            'false_negatives': self.metrics.false_negatives,
            'precision': self.metrics.precision,
            'recall': self.metrics.recall,
            'f1_score': self.metrics.f1_score,
            'avg_lead_time_hours': self.metrics.avg_lead_time_hours,
            'lead_time_samples': len(self.metrics.lead_times),
            'by_chain': self.metrics.by_chain,
            'by_indicator': self.metrics.by_indicator,
            'timestamp': self.metrics.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.metrics.timestamp).isoformat()
        }
    
    def save_results(self, path: str = None):
        """Save replay results to disk"""
        path = path or "/home/ubuntu/.openclaw/workspace/pennyshield/replay/results.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        data = {
            'metrics': self.get_metrics_summary(),
            'results': [
                {
                    'token_address': r.token.token_address,
                    'chain': r.token.chain,
                    'token_symbol': r.token.token_symbol,
                    'outcome': r.token.outcome,
                    'risk_score': r.risk_score.to_dict(),
                    'lead_time_hours': r.lead_time_hours,
                    'is_true_positive': r.is_true_positive,
                    'is_false_positive': r.is_false_positive,
                    'is_true_negative': r.is_true_negative,
                    'is_false_negative': r.is_false_negative,
                    'triggered_indicators': r.triggered_indicators
                }
                for r in self.replay_results
            ]
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def print_summary(self):
        """Print validation summary"""
        m = self.metrics
        print(f"\n{'='*60}")
        print(f"PENNYSHIELD VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total tokens tested: {m.total_tokens}")
        print(f"True Positives:  {m.true_positives}")
        print(f"False Positives: {m.false_positives}")
        print(f"True Negatives:  {m.true_negatives}")
        print(f"False Negatives: {m.false_negatives}")
        print(f"Precision:       {m.precision:.1%}")
        print(f"Recall:          {m.recall:.1%}")
        print(f"F1 Score:        {m.f1_score:.1%}")
        print(f"Avg Lead Time:   {m.avg_lead_time_hours:.1f} hours ({len(m.lead_times)} samples)")
        print(f"\nBy Chain:")
        for chain, stats in m.by_chain.items():
            total = stats['total']
            if total > 0:
                prec = stats['tp'] / (stats['tp'] + stats['fp']) if (stats['tp'] + stats['fp']) > 0 else 0
                rec = stats['tp'] / (stats['tp'] + stats['fn']) if (stats['tp'] + stats['fn']) > 0 else 0
                print(f"  {chain}: {total} tokens, precision={prec:.1%}, recall={rec:.1%}")
        print(f"\nBy Indicator:")
        for ind, stats in sorted(m.by_indicator.items(), key=lambda x: -x[1]['triggered']):
            if stats['triggered'] > 0:
                print(f"  {ind}: triggered {stats['triggered']}x, TP={stats['tp']}, FP={stats['fp']}")


# === Scenario-Based Testing ===
class ScenarioTester:
    """Test specific attack scenarios with synthetic data"""
    
    def __init__(self, replay: HistoricalReplay):
        self.replay = replay
    
    def test_coordinated_launch(self) -> ReplayResult:
        """Test coordinated launch with bundled buys, shared funder, and subsequent distribution"""
        token = HistoricalToken(
            token_address="0xtest1",
            chain="solana",
            token_symbol="TEST1",
            token_name="Test Coordinated Launch",
            launch_timestamp=time.time() - 86400,
            outcome="rug",
            outcome_timestamp=time.time() - 3600,
            pool_data={'liquidity_usd': 50000, 'previous_liquidity_usd': 50000},
            token_data={
                'creator': '0xdeployer1',
                'total_supply': 1_000_000_000,
                'launch_block': 100,
                'holders': [
                    {'address': f'0xwallet{i}', 'amount': 50_000_000} for i in range(10)
                ] + [
                    {'address': f'0xbuyer{i}', 'amount': 5_000_000} for i in range(50)
                ]
            },
            transactions=[
                # Launch bundled buys
                {'block': 100, 'buyer': f'0xwallet{i}', 'token_amount': 50_000_000, 'from': f'0xwallet{i}', 'type': 'buy'}
                for i in range(10)
            ] + [
                # Subsequent sells by same wallets (distribution)
                {'block': 105, 'buyer': f'0xbuyer{i}', 'from': f'0xwallet{i}', 'token_amount': 10_000_000, 'type': 'sell', 'volume_usd': 5000}
                for i in range(10)
            ] + [
                # Organic buyers
                {'block': 110 + i, 'buyer': f'0xbuyer{i}', 'from': f'0xbuyer{i}', 'token_amount': 5_000_000, 'type': 'buy', 'volume_usd': 2500}
                for i in range(50)
            ],
            wallet_graph={
                'edges': [
                    # Shared funder edges
                    {'from': '0xfunder1', 'to': f'0xwallet{i}', 'type': 'funded', 'weight': 1.0, 'evidence': {'tx_hash': f'0xtx{i}'}}
                    for i in range(10)
                ] + [
                    # Co-trading edges between launch wallets
                    {'from': f'0xwallet{i}', 'to': f'0xwallet{(i+1)%10}', 'type': 'co_traded', 'weight': 0.5}
                    for i in range(10)
                ]
            }
        )
        
        return self.replay._replay_token(token)
    
    def test_legitimate_launch(self) -> ReplayResult:
        """Test legitimate organic launch"""
        token = HistoricalToken(
            token_address="0xtest2",
            chain="base",
            token_symbol="TEST2",
            token_name="Test Legitimate Launch",
            launch_timestamp=time.time() - 86400,
            outcome="legitimate",
            pool_data={'liquidity_usd': 200000, 'pool_age_hours': 48},
            token_data={
                'creator': '0xdeployer2',
                'total_supply': 1_000_000_000,
                'launch_block': 100,
                'holders': [
                    {'address': f'0xbuyer{i}', 'amount': 10_000_000} for i in range(100)
                ]
            },
            transactions=[
                {'block': 100 + i, 'buyer': f'0xbuyer{i}', 'token_amount': 10_000_000, 'from': f'0xbuyer{i}'}
                for i in range(100)
            ],
            wallet_graph={'edges': []}
        )
        
        return self.replay._replay_token(token)
    
    def test_liquidity_drain(self) -> ReplayResult:
        """Test gradual liquidity drain"""
        token = HistoricalToken(
            token_address="0xtest3",
            chain="base",
            token_symbol="TEST3",
            token_name="Test Liquidity Drain",
            launch_timestamp=time.time() - 172800,
            outcome="rug",
            outcome_timestamp=time.time() - 3600,
            pool_data={'liquidity_usd': 10000, 'previous_liquidity_usd': 100000},
            token_data={
                'creator': '0xdeployer3',
                'total_supply': 1_000_000_000,
                'holders': [
                    {'address': f'0xwallet{i}', 'amount': 50_000_000} for i in range(5)
                ] + [
                    {'address': f'0xbuyer{i}', 'amount': 5_000_000} for i in range(20)
                ]
            },
            transactions=[
                {'type': 'burn', 'amount_usd': 50000, 'sender': '0xdeployer3', 'timestamp': time.time() - 7200}
            ] + [
                {'type': 'sell', 'volume_usd': 20000, 'sender': f'0xwallet{i}', 'timestamp': time.time() - 3600}
                for i in range(5)
            ],
            wallet_graph={'edges': []}
        )
        
        return self.replay._replay_token(token)
    
    def run_all_scenarios(self) -> List[ReplayResult]:
        """Run all built-in scenarios"""
        results = [
            self.test_coordinated_launch(),
            self.test_legitimate_launch(),
            self.test_liquidity_drain()
        ]
        return results