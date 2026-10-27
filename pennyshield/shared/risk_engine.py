"""
Shared Risk Engine - Core detection logic reusable across chains
"""
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import hashlib
import os
from .operator_graph import OperatorIntelligenceGraph

# === Risk Indicators ===
class RiskIndicator:
    """Base class for risk indicators"""
    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight
    
    def evaluate(self, context: 'DetectionContext') -> 'IndicatorResult':
        raise NotImplementedError

@dataclass
class IndicatorResult:
    indicator: str
    triggered: bool
    confidence: float  # 0.0 - 1.0
    evidence: Dict[str, Any]
    explanation: str

@dataclass
class DetectionContext:
    """Context passed to all indicators during evaluation"""
    token_address: str
    chain: str  # 'solana' or 'base'
    pool_data: Dict[str, Any]
    token_data: Dict[str, Any]
    transactions: List[Dict[str, Any]]
    wallet_graph: 'WalletGraph'
    historical_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WalletGraph:
    """Graph of wallet relationships"""
    nodes: Dict[str, 'WalletNode'] = field(default_factory=dict)
    edges: Dict[str, List['WalletEdge']] = field(default_factory=lambda: defaultdict(list))
    
    def add_wallet(self, address: str, **attrs) -> 'WalletNode':
        if address not in self.nodes:
            self.nodes[address] = WalletNode(address=address, **attrs)
        return self.nodes[address]
    
    def add_edge(self, from_addr: str, to_addr: str, edge_type: str, **attrs):
        edge = WalletEdge(from_addr=from_addr, to_addr=to_addr, edge_type=edge_type, **attrs)
        self.edges[from_addr].append(edge)
        # Also add reverse for undirected queries
        self.edges[to_addr].append(WalletEdge(from_addr=to_addr, to_addr=from_addr, edge_type=edge_type, **attrs))

@dataclass
class WalletNode:
    address: str
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    tokens_held: Dict[str, float] = field(default_factory=dict)  # token -> amount
    funding_sources: List[str] = field(default_factory=list)  # addresses that funded this wallet
    funded_wallets: List[str] = field(default_factory=list)
    deployer_of: List[str] = field(default_factory=list)  # tokens deployed
    total_volume_usd: float = 0.0
    total_trades: int = 0
    cluster_id: Optional[str] = None
    risk_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WalletEdge:
    from_addr: str
    to_addr: str
    edge_type: str  # 'funded', 'same_funder', 'co_traded', 'deployed', 'transferred'
    weight: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

# === Risk Scoring ===
class RiskScorer:
    """Combines multiple indicators into an overall risk score"""
    
    def __init__(self, indicators: List[RiskIndicator], threshold: float = 0.7):
        self.indicators = indicators
        self.threshold = threshold
    
    def score(self, context: DetectionContext) -> 'RiskScore':
        results = []
        total_weight = 0.0
        weighted_sum = 0.0
        
        for indicator in self.indicators:
            result = indicator.evaluate(context)
            results.append(result)
            total_weight += indicator.weight
            weighted_sum += result.confidence * indicator.weight
        
        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        triggered = [r for r in results if r.triggered]
        
        return RiskScore(
            overall_score=overall,
            threshold=self.threshold,
            is_high_risk=overall >= self.threshold,
            indicator_results=results,
            triggered_indicators=[r.indicator for r in triggered],
            timestamp=time.time()
        )

@dataclass
class RiskScore:
    overall_score: float
    threshold: float
    is_high_risk: bool
    indicator_results: List[IndicatorResult]
    triggered_indicators: List[str]
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'overall_score': self.overall_score,
            'threshold': self.threshold,
            'is_high_risk': self.is_high_risk,
            'triggered_indicators': self.triggered_indicators,
            'indicators': [
                {
                    'indicator': r.indicator,
                    'triggered': r.triggered,
                    'confidence': r.confidence,
                    'evidence': r.evidence,
                    'explanation': r.explanation
                }
                for r in self.indicator_results
            ],
            'timestamp': self.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.timestamp).isoformat()
        }

# === Evidence Store ===
class EvidenceStore:
    """Persistent store for detection evidence, outcomes, and learning"""
    
    def __init__(self, store_dir: str = "/home/ubuntu/.openclaw/workspace/pennyshield/evidence"):
        self.store_dir = store_dir
        os.makedirs(store_dir, exist_ok=True)
        self.operator_graph = OperatorIntelligenceGraph(os.path.join(store_dir, "operator_graph.json"))
        self.index_path = os.path.join(store_dir, "index.json")
        self._load_index()
    
    def _load_index(self):
        if os.path.exists(self.index_path):
            with open(self.index_path, 'r') as f:
                self.index = json.load(f)
        else:
            self.index = {"tokens": {}, "wallets": {}, "operators": {}, "runs": []}
    
    def _save_index(self):
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def record_detection(self, token_address: str, chain: str, risk_score: RiskScore, 
                         pool_data: Dict, token_data: Dict):
        """Record a detection event with full evidence"""
        # --- Deterministic Identity Logic ---
        # Normalize basic fields
        norm_chain = chain.lower().strip()
        norm_token = token_address.lower().strip()
        
        tx_hash = pool_data.get('transaction_hash')
        log_index = pool_data.get('log_index')
        block_num = pool_data.get('block_number')
        
        dedup_status = 'stable'
        if tx_hash and log_index is not None:
            # Preferred: Event-level identity
            identity_str = f"{norm_chain}:{tx_hash}:{log_index}"
        elif block_num is not None:
            # Fallback: Token-block level identity
            identity_str = f"{norm_chain}:{norm_token}:{block_num}:pool_creation"
        else:
            # Last resort: Unstable timestamp-based identity
            identity_str = f"{norm_chain}:{norm_token}:{risk_score.timestamp}"
            dedup_status = 'unstable'
            
        detection_id = hashlib.sha256(identity_str.encode()).hexdigest()[:16]
        # ------------------------------------
        
        record = {
            'detection_id': detection_id,
            'token_address': token_address,
            'chain': chain,
            'timestamp': risk_score.timestamp,
            'timestamp_iso': datetime.fromtimestamp(risk_score.timestamp).isoformat(),
            'risk_score': risk_score.to_dict(),
            'pool_snapshot': pool_data,
            'token_snapshot': token_data,
            'outcome': None,  # To be filled later
            'outcome_timestamp': None,
            'metadata': {'deduplication_status': dedup_status}
        }
        
        # Save detailed record
        detail_path = os.path.join(self.store_dir, f"{detection_id}.json")
        with open(detail_path, 'w') as f:
            json.dump(record, f, indent=2)
        
        # Update index
        if token_address not in self.index['tokens']:
            self.index['tokens'][token_address] = []
        if detection_id not in self.index['tokens'][token_address]:
            self.index['tokens'][token_address].append(detection_id)
        
        # Auto-link deployer as operator for cross-token intelligence
        deployer = token_data.get('creator') or token_data.get('deployer')
        graph_evidence = {
            'detection_id': detection_id,
            'chain': chain,
            'signature': tx_hash,
            'slot': pool_data.get('block_number'),
            'timestamp': pool_data.get('block_time') or risk_score.timestamp,
            'name': token_data.get('name'),
            'symbol': token_data.get('symbol'),
        }
        funding_sources = (token_data.get('funding_sources') or
                           token_data.get('funding_wallets') or [])
        if isinstance(funding_sources, (str, dict)):
            funding_sources = [funding_sources]
        if token_data.get('funding_source'):
            funding_sources = list(funding_sources) + [token_data['funding_source']]
        self.operator_graph.record_launch(
            chain, token_address, deployer or '', detection_id,
            graph_evidence, funding_sources=funding_sources
        )
        if deployer:
            operator_sig = f"deployer:{deployer}"
            if operator_sig not in self.index['operators']:
                self.index['operators'][operator_sig] = []
            history = self.index['operators'][operator_sig]
            existing = next((entry for entry in history
                             if entry.get('detection_id') == detection_id), None)
            if existing is None:
                history.append({
                    'detection_id': detection_id,
                    'token_address': token_address,
                    'chain': chain,
                    'risk_score': risk_score.overall_score,
                    'linked_at': time.time()
                })
            else:
                existing.update({
                    'token_address': token_address,
                    'chain': chain,
                    'risk_score': risk_score.overall_score,
                })
        
        # Auto-link wallet clusters
        for ind_result in risk_score.indicator_results:
            if ind_result.indicator == 'wallet_clustering' and ind_result.evidence.get('clusters'):
                for cluster in ind_result.evidence['clusters']:
                    cluster_id = cluster.get('cluster_id')
                    if cluster_id:
                        self.record_wallet_cluster(cluster_id, cluster['wallets'], {
                            'token': token_address,
                            'evidence': cluster,
                            'operator_signature': f"deployer:{deployer}" if deployer else None
                        })
        
        self._save_index()
        
        return detection_id
    
    def record_outcome(self, detection_id: str, outcome: str, 
                       details: Dict[str, Any] = None):
        """Record the eventual outcome of a detection"""
        detail_path = os.path.join(self.store_dir, f"{detection_id}.json")
        if os.path.exists(detail_path):
            with open(detail_path, 'r') as f:
                record = json.load(f)
            
            record['outcome'] = outcome
            record['outcome_timestamp'] = time.time()
            record['outcome_timestamp_iso'] = datetime.fromtimestamp(record['outcome_timestamp']).isoformat()
            if details:
                record['outcome_details'] = details

            self.operator_graph.record_outcome(
                record.get('chain', ''), record.get('token_address', ''),
                detection_id, outcome, record['outcome_timestamp'], details
            )
            
            with open(detail_path, 'w') as f:
                json.dump(record, f, indent=2)
            
            # Also update operator history with outcome
            deployer = record.get('token_snapshot', {}).get('creator') or record.get('token_snapshot', {}).get('deployer')
            if deployer:
                operator_sig = f"deployer:{deployer}"
                if operator_sig in self.index['operators']:
                    for op_entry in self.index['operators'][operator_sig]:
                        if op_entry.get('detection_id') == detection_id:
                            op_entry['outcome'] = outcome
                            op_entry['outcome_timestamp'] = time.time()
                            self._save_index()
                            break
    
    def record_wallet_cluster(self, cluster_id: str, wallets: List[str], 
                              evidence: Dict[str, Any]):
        """Record a detected wallet cluster"""
        if cluster_id not in self.index['wallets']:
            self.index['wallets'][cluster_id] = []
        
        cluster_record = {
            'cluster_id': cluster_id,
            'wallets': wallets,
            'evidence': evidence,
            'first_detected': time.time(),
            'tokens_involved': evidence.get('tokens', []),
            'operator_signature': evidence.get('operator_signature')
        }
        
        self.index['wallets'][cluster_id].append(cluster_record)
        self._save_index()
    
    def get_operator_history(self, operator_signature: str) -> List[Dict]:
        """Get all detections linked to an operator signature"""
        if operator_signature not in self.index['operators']:
            self.index['operators'][operator_signature] = []
        return self.index['operators'][operator_signature]

    def get_operator_graph(self, operator_signature: str, depth: int = 3,
                           limit: int = 500) -> Dict[str, Any]:
        """Get evidence-backed wallet, launch, and outcome links for an operator."""
        prefix = 'deployer:'
        address = operator_signature[len(prefix):] if operator_signature.startswith(prefix) else operator_signature
        return self.operator_graph.get_subgraph(
            self.operator_graph.wallet_id(address), depth=depth, limit=limit
        )
    
    def link_to_operator(self, detection_id: str, operator_signature: str):
        """Link a detection to a known operator"""
        if operator_signature not in self.index['operators']:
            self.index['operators'][operator_signature] = []
        self.index['operators'][operator_signature].append({
            'detection_id': detection_id,
            'linked_at': time.time()
        })
        self._save_index()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detection statistics for validation"""
        total = 0
        high_risk = 0
        outcomes = {'rug': 0, 'legitimate': 0, 'unknown': 0}
        early_warnings = 0
        
        for token, detections in self.index['tokens'].items():
            for det_id in detections:
                detail_path = os.path.join(self.store_dir, f"{det_id}.json")
                if os.path.exists(detail_path):
                    with open(detail_path, 'r') as f:
                        record = json.load(f)
                    total += 1
                    if record['risk_score']['is_high_risk']:
                        high_risk += 1
                    outcome = record.get('outcome')
                    if outcome in outcomes:
                        outcomes[outcome] += 1
                    else:
                        outcomes['unknown'] += 1
                    # Check if warning came before major price drop
                    if outcome == 'rug' and record.get('outcome_timestamp'):
                        # Simplified: if detection was > 1 hour before outcome
                        if record['outcome_timestamp'] - record['timestamp'] > 3600:
                            early_warnings += 1
        
        return {
            'total_detections': total,
            'high_risk_count': high_risk,
            'high_risk_rate': high_risk / total if total > 0 else 0,
            'outcomes': outcomes,
            'early_warnings': early_warnings,
            'early_warning_rate': early_warnings / outcomes['rug'] if outcomes['rug'] > 0 else 0
        }
