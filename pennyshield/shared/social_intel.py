"""
Social Manipulation Intelligence Module
========================================
Detects manufactured popularity and coordinated social activity
that may indicate manipulation designed to trigger FOMO.
"""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib
import re
import os

from .risk_engine import RiskIndicator, IndicatorResult, DetectionContext, EvidenceStore


# === Social Data Source Interface ===
class SocialDataSource:
    """Base class for social data sources"""
    
    def __init__(self, name: str, rate_limit_per_min: int = 30):
        self.name = name
        self.rate_limit_per_min = rate_limit_per_min
        self.last_request_time = 0
        self.request_count = 0
    
    def fetch_token_mentions(self, token_address: str, 
                             token_symbol: str = None,
                             window_hours: int = 24) -> List[Dict]:
        """Fetch social mentions for a token"""
        raise NotImplementedError
    
    def fetch_account_history(self, account_id: str, 
                              window_hours: int = 168) -> List[Dict]:
        """Fetch account posting history"""
        raise NotImplementedError
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        now = time.time()
        if now - self.last_request_time < 60:
            if self.request_count >= self.rate_limit_per_min:
                raise Exception(f"Rate limit exceeded for {self.name}")
        else:
            self.request_count = 0
            self.last_request_time = now
        self.request_count += 1


class MockSocialSource(SocialDataSource):
    """Mock social source for testing - replace with real APIs"""
    
    def fetch_token_mentions(self, token_address: str, 
                             token_symbol: str = None,
                             window_hours: int = 24) -> List[Dict]:
        """Return mock mentions for testing"""
        # In production, this would query Twitter/X, Telegram, Discord, etc.
        return []
    
    def fetch_account_history(self, account_id: str, 
                              window_hours: int = 168) -> List[Dict]:
        return []


# === Social Signal Data Structures ===
@dataclass
class SocialMention:
    """A single social media mention/post"""
    platform: str  # 'twitter', 'telegram', 'discord', etc.
    account_id: str
    account_display_name: str
    content: str
    url: str
    timestamp: float
    engagement: Dict[str, int] = field(default_factory=dict)  # likes, retweets, replies, views
    token_addresses: List[str] = field(default_factory=list)
    token_symbols: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    media_urls: List[str] = field(default_factory=list)
    raw_data: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'platform': self.platform,
            'account_id': self.account_id,
            'account_display_name': self.account_display_name,
            'content': self.content,
            'url': self.url,
            'timestamp': self.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.timestamp).isoformat(),
            'engagement': self.engagement,
            'token_addresses': self.token_addresses,
            'token_symbols': self.token_symbols,
            'links': self.links,
            'media_urls': self.media_urls
        }


@dataclass
class SocialCluster:
    """A cluster of coordinated social accounts"""
    cluster_id: str
    accounts: List[str]
    common_content_hashes: List[str]
    time_window: Tuple[float, float]
    coordination_score: float
    shared_links: List[str]
    repeated_phrases: List[str]
    launch_correlation: List[str]  # token addresses they've promoted together
    first_seen: float
    last_seen: float
    
    def to_dict(self) -> Dict:
        return {
            'cluster_id': self.cluster_id,
            'accounts': self.accounts,
            'common_content_hashes': self.common_content_hashes,
            'time_window': self.time_window,
            'coordination_score': self.coordination_score,
            'shared_links': self.shared_links,
            'repeated_phrases': self.repeated_phrases,
            'launch_correlation': self.launch_correlation,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen
        }


@dataclass
class SocialAnomaly:
    """Anomaly in social activity for a token"""
    token_address: str
    anomaly_type: str  # 'view_spike', 'mention_spike', 'engagement_spike', 'coordinated_callout'
    severity: float  # 0.0 - 1.0
    baseline: float
    observed: float
    multiplier: float
    time_window: Tuple[float, float]
    details: Dict
    data_limitation: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'token_address': self.token_address,
            'anomaly_type': self.anomaly_type,
            'severity': self.severity,
            'baseline': self.baseline,
            'observed': self.observed,
            'multiplier': self.multiplier,
            'time_window': self.time_window,
            'details': self.details,
            'data_limitation': self.data_limitation
        }


# === Social Manipulation Detectors ===
class AttentionAnomalyDetector(RiskIndicator):
    """Detect abnormal attention spikes (views, mentions, engagement)"""
    
    def __init__(self, spike_threshold: float = 5.0, 
                 min_baseline_mentions: int = 10,
                 window_hours: int = 6):
        super().__init__("attention_anomaly", weight=1.5)
        self.spike_threshold = spike_threshold
        self.min_baseline_mentions = min_baseline_mentions
        self.window_hours = window_hours
    
    def evaluate(self, context: DetectionContext) -> IndicatorResult:
        token_address = context.token_address
        social_data = context.metadata.get('social_data', {})
        
        if not social_data:
            return IndicatorResult(
                indicator=self.name,
                triggered=False,
                confidence=0.0,
                evidence={'reason': 'no_social_data', 'data_limitation': 'social_data_source_unavailable'},
                explanation="No social data available for attention analysis"
            )
        
        mentions = social_data.get('mentions', [])
        if len(mentions) < self.min_baseline_mentions:
            return IndicatorResult(
                indicator=self.name,
                triggered=False,
                confidence=0.0,
                evidence={
                    'reason': 'insufficient_baseline',
                    'mention_count': len(mentions),
                    'min_required': self.min_baseline_mentions,
                    'data_limitation': 'insufficient_social_data_for_baseline'
                },
                explanation=f"Insufficient mentions ({len(mentions)}) for baseline calculation"
            )
        
        # Calculate baseline from older mentions (outside current window)
        now = time.time()
        window_start = now - (self.window_hours * 3600)
        baseline_window_start = now - (self.window_hours * 3600 * 4)  # 4x window for baseline
        
        recent_mentions = [m for m in mentions if m.timestamp >= window_start]
        baseline_mentions = [m for m in mentions if baseline_window_start <= m.timestamp < window_start]
        
        if not baseline_mentions:
            return IndicatorResult(
                indicator=self.name,
                triggered=False,
                confidence=0.0,
                evidence={'reason': 'no_baseline_window', 'data_limitation': 'insufficient_historical_data'},
                explanation="No baseline period available"
            )
        
        # Compare mention rates
        recent_rate = len(recent_mentions) / self.window_hours
        baseline_rate = len(baseline_mentions) / (self.window_hours * 3)  # 3x window
        
        if baseline_rate == 0:
            multiplier = float('inf') if recent_rate > 0 else 1.0
        else:
            multiplier = recent_rate / baseline_rate
        
        # Also check engagement spikes
        recent_engagement = sum(
            sum(m.engagement.values()) for m in recent_mentions
        )
        baseline_engagement = sum(
            sum(m.engagement.values()) for m in baseline_mentions
        ) / 3 if baseline_mentions else 0
        
        engagement_multiplier = (recent_engagement / baseline_engagement) if baseline_engagement > 0 else 1.0
        
        triggered = multiplier >= self.spike_threshold or engagement_multiplier >= self.spike_threshold
        confidence = min(max(multiplier, engagement_multiplier) / self.spike_threshold, 1.0)
        
        data_limitation = None
        if social_data.get('data_source') == 'mock':
            data_limitation = 'using_mock_social_data_not_real_apis'
        
        return IndicatorResult(
            indicator=self.name,
            triggered=triggered,
            confidence=confidence,
            evidence={
                'recent_mention_count': len(recent_mentions),
                'baseline_mention_count': len(baseline_mentions),
                'recent_mention_rate_per_hour': recent_rate,
                'baseline_mention_rate_per_hour': baseline_rate,
                'mention_spike_multiplier': multiplier,
                'recent_total_engagement': recent_engagement,
                'baseline_total_engagement': baseline_engagement,
                'engagement_spike_multiplier': engagement_multiplier,
                'spike_threshold': self.spike_threshold,
                'window_hours': self.window_hours,
                'data_limitation': data_limitation
            },
            explanation=self._build_explanation(triggered, multiplier, engagement_multiplier, data_limitation)
        )
    
    def _build_explanation(self, triggered: bool, mention_mult: float, 
                           engagement_mult: float, data_limitation: str = None) -> str:
        if not triggered:
            return "No attention anomaly detected"
        parts = []
        if mention_mult >= self.spike_threshold:
            parts.append(f"mention rate {mention_mult:.1f}x baseline")
        if engagement_mult >= self.spike_threshold:
            parts.append(f"engagement {engagement_mult:.1f}x baseline")
        if data_limitation:
            parts.append(f"({data_limitation})")
        return "Attention spike: " + "; ".join(parts)


class CalloutCoordinationDetector(RiskIndicator):
    """Detect coordinated callouts across multiple accounts"""
    
    def __init__(self, min_accounts: int = 3,
                 time_window_minutes: int = 60,
                 content_similarity_threshold: float = 0.7):
        super().__init__("callout_coordination", weight=2.0)
        self.min_accounts = min_accounts
        self.time_window_minutes = time_window_minutes
        self.content_similarity_threshold = content_similarity_threshold
    
    def evaluate(self, context: DetectionContext) -> IndicatorResult:
        token_address = context.token_address
        social_data = context.metadata.get('social_data', {})
        
        if not social_data:
            return IndicatorResult(
                indicator=self.name,
                triggered=False,
                confidence=0.0,
                evidence={'reason': 'no_social_data', 'data_limitation': 'social_data_source_unavailable'},
                explanation="No social data available for callout analysis"
            )
        
        mentions = social_data.get('mentions', [])
        if len(mentions) < self.min_accounts:
            return IndicatorResult(
                indicator=self.name,
                triggered=False,
                confidence=0.0,
                evidence={'mention_count': len(mentions), 'min_required': self.min_accounts},
                explanation="Insufficient mentions for coordination analysis"
            )
        
        # Filter mentions for this token
        token_mentions = [
            m for m in mentions 
            if token_address in m.token_addresses or 
               (m.token_symbols and any(s in context.token_data.get('symbol', '') for s in m.token_symbols))
        ]
        
        if len(token_mentions) < self.min_accounts:
            return IndicatorResult(
                indicator=self.name,
                triggered=False,
                confidence=0.0,
                evidence={'token_mention_count': len(token_mentions), 'min_required': self.min_accounts},
                explanation="Insufficient token-specific mentions"
            )
        
        # Sort by timestamp
        token_mentions.sort(key=lambda m: m.timestamp)
        
        # Find clusters of similar posts within time window
        clusters = self._find_coordinated_clusters(token_mentions)
        
        # Filter significant clusters
        significant = [c for c in clusters if len(c.accounts) >= self.min_accounts]
        
        # Check for cross-launch recurrence
        cross_launch = self._check_cross_launch_recurrence(significant, social_data)
        
        triggered = len(significant) > 0
        confidence = min(len(significant) * 0.25 + (0.3 if cross_launch else 0), 1.0)
        
        data_limitation = None
        if social_data.get('data_source') == 'mock':
            data_limitation = 'using_mock_social_data_not_real_apis'
        
        return IndicatorResult(
            indicator=self.name,
            triggered=triggered,
            confidence=confidence,
            evidence={
                'total_token_mentions': len(token_mentions),
                'clusters_found': len(clusters),
                'significant_clusters': len(significant),
                'clusters': [c.to_dict() for c in significant],
                'cross_launch_recurrence': cross_launch,
                'min_accounts': self.min_accounts,
                'time_window_minutes': self.time_window_minutes,
                'similarity_threshold': self.content_similarity_threshold,
                'data_limitation': data_limitation
            },
            explanation=self._build_explanation(triggered, significant, cross_launch, data_limitation)
        )
    
    def _find_coordinated_clusters(self, mentions: List[SocialMention]) -> List[SocialCluster]:
        """Find clusters of similar posts within time window"""
        clusters = []
        used = set()
        
        for i, m1 in enumerate(mentions):
            if i in used:
                continue
            
            cluster_accounts = [m1.account_id]
            cluster_content = [m1.content]
            cluster_links = set(m1.links)
            cluster_phrases = self._extract_phrases(m1.content)
            start_time = m1.timestamp
            end_time = m1.timestamp
            
            # Look for similar posts within time window
            for j, m2 in enumerate(mentions[i+1:], i+1):
                if j in used:
                    continue
                if m2.timestamp - m1.timestamp > self.time_window_minutes * 60:
                    break
                
                similarity = self._content_similarity(m1.content, m2.content)
                if similarity >= self.content_similarity_threshold:
                    cluster_accounts.append(m2.account_id)
                    cluster_content.append(m2.content)
                    cluster_links.update(m2.links)
                    cluster_phrases = self._common_phrases(cluster_phrases, self._extract_phrases(m2.content))
                    end_time = m2.timestamp
                    used.add(j)
            
            if len(cluster_accounts) >= self.min_accounts:
                # Generate cluster ID
                cluster_id = hashlib.sha256(
                    f"{mentions[0].token_addresses[0] if mentions else 'unknown'}"
                    f"{start_time}{'-'.join(sorted(cluster_accounts))}".encode()
                ).hexdigest()[:12]
                
                clusters.append(SocialCluster(
                    cluster_id=cluster_id,
                    accounts=cluster_accounts,
                    common_content_hashes=[hashlib.md5(c.encode()).hexdigest()[:8] for c in cluster_content],
                    time_window=(start_time, end_time),
                    coordination_score=len(cluster_accounts) / len(mentions),
                    shared_links=list(cluster_links),
                    repeated_phrases=cluster_phrases,
                    launch_correlation=[],  # Would be filled by cross-launch check
                    first_seen=start_time,
                    last_seen=end_time
                ))
        
        return clusters
    
    def _content_similarity(self, text1: str, text2: str) -> float:
        """Simple content similarity using Jaccard index on words"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)
    
    def _extract_phrases(self, text: str) -> List[str]:
        """Extract significant phrases (3-5 words)"""
        words = text.lower().split()
        phrases = []
        for i in range(len(words) - 2):
            for length in [3, 4, 5]:
                if i + length <= len(words):
                    phrase = ' '.join(words[i:i+length])
                    if len(phrase) > 10:  # Skip very short phrases
                        phrases.append(phrase)
        return phrases
    
    def _common_phrases(self, phrases1: List[str], phrases2: List[str]) -> List[str]:
        """Find common phrases between two lists"""
        set1 = set(phrases1)
        set2 = set(phrases2)
        return list(set1 & set2)
    
    def _check_cross_launch_recurrence(self, clusters: List[SocialCluster], 
                                        social_data: Dict) -> bool:
        """Check if same account clusters appear around other launches"""
        # This would check historical data for recurring clusters
        # For now, return False - would need historical social data
        return False
    
    def _build_explanation(self, triggered: bool, clusters: List[SocialCluster], 
                           cross_launch: bool, data_limitation: str = None) -> str:
        if not triggered:
            return "No coordinated callout pattern detected"
        parts = [f"{len(clusters)} coordinated callout cluster(s)"]
        for c in clusters:
            parts.append(f"{len(c.accounts)} accounts, {len(c.repeated_phrases)} shared phrases")
        if cross_launch:
            parts.append("cluster seen in previous launches")
        if data_limitation:
            parts.append(f"({data_limitation})")
        return "; ".join(parts)


class PopularityRealityGapDetector(RiskIndicator):
    """Compare social popularity with on-chain reality"""
    
    def __init__(self, min_buyer_ratio: float = 0.1,
                 max_concentration_for_social: float = 0.5):
        super().__init__("popularity_reality_gap", weight=2.0)
        self.min_buyer_ratio = min_buyer_ratio
        self.max_concentration_for_social = max_concentration_for_social
    
    def evaluate(self, context: DetectionContext) -> IndicatorResult:
        token_address = context.token_address
        social_data = context.metadata.get('social_data', {})
        
        if not social_data:
            return IndicatorResult(
                indicator=self.name,
                triggered=False,
                confidence=0.0,
                evidence={'reason': 'no_social_data', 'data_limitation': 'social_data_source_unavailable'},
                explanation="No social data for popularity comparison"
            )
        
        mentions = social_data.get('mentions', [])
        unique_accounts = set(m.account_id for m in mentions)
        
        # On-chain metrics
        onchain = context.metadata.get('onchain_metrics', {})
        unique_buyers = onchain.get('unique_buyers_24h', 0)
        net_buy_volume = onchain.get('net_buy_volume_usd_24h', 0)
        holder_concentration = onchain.get('top_10_holder_pct', 0)
        liquidity_usd = context.pool_data.get('liquidity_usd', 0)
        
        # Calculate ratios
        mention_count = len(mentions)
        account_count = len(unique_accounts)
        
        # Buyer-to-mention ratio
        buyer_ratio = unique_buyers / account_count if account_count > 0 else 0
        
        # Social vs liquidity
        social_per_liquidity = mention_count / (liquidity_usd / 1000) if liquidity_usd > 0 else 0
        
        # Check for gap
        triggered = False
        confidence = 0.0
        reasons = []
        
        if buyer_ratio < self.min_buyer_ratio and account_count > 20:
            triggered = True
            confidence = max(confidence, 1.0 - buyer_ratio / self.min_buyer_ratio)
            reasons.append(f"only {unique_buyers} unique buyers for {account_count} mentioning accounts ({buyer_ratio:.1%})")
        
        if holder_concentration > self.max_concentration_for_social and mention_count > 50:
            triggered = True
            confidence = max(confidence, min(holder_concentration / self.max_concentration_for_social, 1.0))
            reasons.append(f"high holder concentration ({holder_concentration:.1%}) despite high social mentions ({mention_count})")
        
        if net_buy_volume < 0 and mention_count > 30:
            triggered = True
            confidence = max(confidence, 0.8)
            reasons.append(f"negative net buying (${net_buy_volume:,.0f}) despite high social activity")
        
        data_limitation = None
        if social_data.get('data_source') == 'mock':
            data_limitation = 'using_mock_social_data_not_real_apis'
        
        return IndicatorResult(
            indicator=self.name,
            triggered=triggered,
            confidence=min(confidence, 1.0),
            evidence={
                'mention_count': mention_count,
                'unique_social_accounts': account_count,
                'unique_onchain_buyers_24h': unique_buyers,
                'buyer_to_account_ratio': buyer_ratio,
                'net_buy_volume_usd_24h': net_buy_volume,
                'top_10_holder_concentration': holder_concentration,
                'liquidity_usd': liquidity_usd,
                'social_mentions_per_1k_liquidity': social_per_liquidity,
                'min_buyer_ratio_threshold': self.min_buyer_ratio,
                'max_concentration_threshold': self.max_concentration_for_social,
                'data_limitation': data_limitation
            },
            explanation=self._build_explanation(triggered, reasons, data_limitation)
        )
    
    def _build_explanation(self, triggered: bool, reasons: List[str], 
                           data_limitation: str = None) -> str:
        if not triggered:
            return "Social popularity aligns with on-chain activity"
        parts = reasons
        if data_limitation:
            parts.append(f"({data_limitation})")
        return "Popularity-reality gap: " + "; ".join(parts)


class CrossLaunchSocialDetector(RiskIndicator):
    """Detect recurring social clusters across multiple suspicious launches"""
    
    def __init__(self, evidence_store: EvidenceStore,
                 min_recurrence: int = 2):
        super().__init__("cross_launch_social", weight=2.5)
        self.evidence_store = evidence_store
        self.min_recurrence = min_recurrence
    
    def evaluate(self, context: DetectionContext) -> IndicatorResult:
        social_data = context.metadata.get('social_data', {})
        
        if not social_data:
            return IndicatorResult(
                indicator=self.name,
                triggered=False,
                confidence=0.0,
                evidence={'reason': 'no_social_data', 'data_limitation': 'social_data_source_unavailable'},
                explanation="No social data for cross-launch analysis"
            )
        
        # Get social clusters for this token
        clusters = social_data.get('clusters', [])
        if not clusters:
            return IndicatorResult(
                indicator=self.name,
                triggered=False,
                confidence=0.0,
                evidence={'reason': 'no_clusters_detected'},
                explanation="No social clusters to analyze for cross-launch patterns"
            )
        
        # Check each cluster against historical data
        recurring_clusters = []
        for cluster in clusters:
            cluster_sig = self._cluster_signature(cluster)
            history = self.evidence_store.get_operator_history(f"social_cluster:{cluster_sig}")
            
            # Filter for clusters linked to rug outcomes
            rug_linked = sum(1 for h in history if h.get('outcome') == 'rug')
            total_linked = len(history)
            
            if total_linked >= self.min_recurrence:
                recurring_clusters.append({
                    'cluster': cluster,
                    'historical_appearances': total_linked,
                    'rug_linked_appearances': rug_linked,
                    'rug_association_rate': rug_linked / total_linked if total_linked > 0 else 0
                })
        
        triggered = len(recurring_clusters) > 0
        confidence = min(len(recurring_clusters) * 0.3, 1.0) if triggered else 0.0
        
        data_limitation = None
        if social_data.get('data_source') == 'mock':
            data_limitation = 'using_mock_social_data_not_real_apis'
        
        return IndicatorResult(
            indicator=self.name,
            triggered=triggered,
            confidence=confidence,
            evidence={
                'recurring_clusters': recurring_clusters,
                'total_clusters_checked': len(clusters),
                'min_recurrence_threshold': self.min_recurrence,
                'data_limitation': data_limitation
            },
            explanation=self._build_explanation(triggered, recurring_clusters, data_limitation)
        )
    
    def _cluster_signature(self, cluster: SocialCluster) -> str:
        """Generate a signature for a social cluster"""
        # Use sorted account IDs and shared phrases
        sig_data = '|'.join(sorted(cluster.accounts)) + '|' + '|'.join(sorted(cluster.repeated_phrases))
        return hashlib.sha256(sig_data.encode()).hexdigest()[:16]
    
    def _build_explanation(self, triggered: bool, recurring: List[Dict], 
                           data_limitation: str = None) -> str:
        if not triggered:
            return "No recurring social clusters detected"
        parts = [f"{len(recurring)} social cluster(s) seen in previous launches"]
        for r in recurring:
            parts.append(f"{r['historical_appearances']} appearances, {r['rug_association_rate']:.1%} rug association")
        if data_limitation:
            parts.append(f"({data_limitation})")
        return "; ".join(parts)


# === Combined Social Risk Scorer ===
def create_social_risk_scorer(evidence_store: EvidenceStore) -> 'RiskScorer':
    """Create a risk scorer for social manipulation detection"""
    from .risk_engine import RiskScorer
    
    indicators = [
        AttentionAnomalyDetector(),
        CalloutCoordinationDetector(),
        PopularityRealityGapDetector(),
        CrossLaunchSocialDetector(evidence_store),
    ]
    return RiskScorer(indicators, threshold=0.6)


# === Social Data Collector ===
class SocialDataCollector:
    """Collects and normalizes social data from multiple sources"""
    
    def __init__(self, sources: List[SocialDataSource] = None):
        self.sources = sources or [MockSocialSource("mock")]
        self.cache: Dict[str, List[SocialMention]] = {}
        self.cache_ttl = 300  # 5 minutes
    
    def collect_token_social_data(self, token_address: str, 
                                  token_symbol: str = None,
                                  token_name: str = None,
                                  window_hours: int = 24) -> Dict[str, Any]:
        """Collect all social data for a token"""
        all_mentions = []
        
        for source in self.sources:
            try:
                mentions_data = source.fetch_token_mentions(
                    token_address, token_symbol, window_hours
                )
                # Convert to SocialMention objects
                for m in mentions_data:
                    mention = SocialMention(
                        platform=m.get('platform', source.name),
                        account_id=m.get('account_id', ''),
                        account_display_name=m.get('account_display_name', ''),
                        content=m.get('content', ''),
                        url=m.get('url', ''),
                        timestamp=m.get('timestamp', time.time()),
                        engagement=m.get('engagement', {}),
                        token_addresses=m.get('token_addresses', [token_address]),
                        token_symbols=m.get('token_symbols', [token_symbol] if token_symbol else []),
                        links=m.get('links', []),
                        media_urls=m.get('media_urls', []),
                        raw_data=m
                    )
                    all_mentions.append(mention)
            except Exception as e:
                print(f"[WARNING] Social source {source.name} failed: {e}")
        
        # Deduplicate
        unique_mentions = self._deduplicate_mentions(all_mentions)
        
        return {
            'mentions': unique_mentions,
            'mention_count': len(unique_mentions),
            'unique_accounts': len(set(m.account_id for m in unique_mentions)),
            'platforms': list(set(m.platform for m in unique_mentions)),
            'collected_at': time.time(),
            'data_source': self.sources[0].name if self.sources else 'none',
            'clusters': []  # Would be populated by CalloutCoordinationDetector
        }
    
    def _deduplicate_mentions(self, mentions: List[SocialMention]) -> List[SocialMention]:
        """Deduplicate mentions by URL or content hash"""
        seen = set()
        unique = []
        for m in mentions:
            key = m.url or hashlib.md5(m.content.encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique


# === Combined Social + On-Chain Risk Assessment ===
class CombinedRiskAssessor:
    """Combines social and on-chain risk assessments"""
    
    def __init__(self, onchain_scorer, social_scorer):
        self.onchain_scorer = onchain_scorer
        self.social_scorer = social_scorer
    
    def assess(self, context: DetectionContext) -> Dict[str, Any]:
        """Run both assessments and combine"""
        # Run on-chain assessment
        onchain_result = self.onchain_scorer.score(context)
        
        # Run social assessment (only if social data available)
        social_result = None
        if context.metadata.get('social_data'):
            social_result = self.social_scorer.score(context)
        
        # Combine scores
        combined_score = onchain_result.overall_score
        if social_result:
            # Weight: 60% on-chain, 40% social when both available
            combined_score = 0.6 * onchain_result.overall_score + 0.4 * social_result.overall_score
        
        # Determine overall risk
        is_high_risk = combined_score >= 0.7
        
        # Agreement analysis
        agreement = self._analyze_agreement(onchain_result, social_result)
        
        return {
            'combined_score': combined_score,
            'is_high_risk': is_high_risk,
            'onchain_score': onchain_result.overall_score,
            'onchain_high_risk': onchain_result.is_high_risk,
            'social_score': social_result.overall_score if social_result else None,
            'social_high_risk': social_result.is_high_risk if social_result else None,
            'agreement': agreement,
            'onchain_indicators': onchain_result.triggered_indicators,
            'social_indicators': social_result.triggered_indicators if social_result else [],
            'timestamp': time.time(),
            'timestamp_iso': datetime.now().isoformat()
        }
    
    def _analyze_agreement(self, onchain: 'RiskScore', social: Optional['RiskScore']) -> Dict:
        """Analyze whether social and on-chain signals agree"""
        if not social:
            return {'type': 'onchain_only', 'agreement': 'unknown'}
        
        onchain_high = onchain.is_high_risk
        social_high = social.is_high_risk
        
        if onchain_high and social_high:
            return {
                'type': 'both_high',
                'agreement': 'strong_concern',
                'description': 'Both social manipulation and on-chain risk signals elevated'
            }
        elif onchain_high and not social_high:
            return {
                'type': 'onchain_only_high',
                'agreement': 'onchain_concern',
                'description': 'On-chain risk elevated but social activity normal'
            }
        elif not onchain_high and social_high:
            return {
                'type': 'social_only_high',
                'agreement': 'social_concern',
                'description': 'Social manipulation signals but on-chain appears normal'
            }
        else:
            return {
                'type': 'both_normal',
                'agreement': 'normal',
                'description': 'Neither social nor on-chain signals elevated'
            }