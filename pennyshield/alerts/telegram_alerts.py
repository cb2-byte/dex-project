"""
PennyShield Alert System
=========================
Telegram alerts with token identifiers, transaction links, timestamps,
risk reasons, confidence and current liquidity conditions.
"""
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import os

from pennyshield.shared.risk_engine import RiskScore, IndicatorResult, EvidenceStore


# === Alert Data Structures ===
@dataclass
class Alert:
    """A PennyShield alert"""
    alert_id: str
    token_address: str
    chain: str  # 'solana', 'base', 'ethereum'
    token_symbol: str
    token_name: str
    alert_type: str  # 'high_risk', 'new_launch', 'liquidity_drain', 'coordinated_distribution', etc.
    severity: str  # 'critical', 'high', 'medium', 'low'
    risk_score: RiskScore
    evidence_summary: Dict[str, Any]
    liquidity_usd: float
    market_cap_usd: Optional[float]
    transaction_links: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False
    outcome: Optional[str] = None  # 'rug', 'legitimate', 'unknown'
    
    def to_dict(self) -> Dict:
        return {
            'alert_id': self.alert_id,
            'token_address': self.token_address,
            'chain': self.chain,
            'token_symbol': self.token_symbol,
            'token_name': self.token_name,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'risk_score': self.risk_score.to_dict(),
            'evidence_summary': self.evidence_summary,
            'liquidity_usd': self.liquidity_usd,
            'market_cap_usd': self.market_cap_usd,
            'transaction_links': self.transaction_links,
            'timestamp': self.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.timestamp).isoformat(),
            'acknowledged': self.acknowledged,
            'outcome': self.outcome
        }


# === Telegram Formatter ===
class TelegramFormatter:
    """Format alerts for Telegram delivery"""
    
    # Emoji mappings
    SEVERITY_EMOJI = {
        'critical': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }
    
    CHAIN_EMOJI = {
        'solana': '🟣',
        'base': '🔵',
        'ethereum': '🔷'
    }
    
    INDICATOR_EMOJI = {
        'early_snipe': '🎯',
        'deployer_intelligence': '👤',
        'wallet_clustering': '🕸️',
        'distribution': '📉',
        'exit_detector': '🚪',
        'new_pool': '🆕',
        'liquidity_drain': '💧',
        'contract_risk': '⚠️',
        'whale_activity': '🐋',
        'deployer_link': '🔗',
        'attention_anomaly': '👁️',
        'callout_coordination': '📢',
        'popularity_reality_gap': '📊',
        'cross_launch_social': '🔄'
    }
    
    @classmethod
    def format_alert(cls, alert: Alert) -> str:
        """Format alert as Telegram message"""
        lines = []
        
        # Header
        severity_emoji = cls.SEVERITY_EMOJI.get(alert.severity, '⚪')
        chain_emoji = cls.CHAIN_EMOJI.get(alert.chain, '⚪')
        
        lines.append(f"{severity_emoji} <b>PENNYSHIELD ALERT</b> {severity_emoji}")
        lines.append(f"{chain_emoji} <b>{alert.token_symbol}</b> ({alert.token_name}) on {alert.chain.title()}")
        lines.append(f"")
        
        # Risk summary
        lines.append(f"<b>Risk Score:</b> {alert.risk_score.overall_score:.1%}")
        lines.append(f"<b>Severity:</b> {alert.severity.upper()}")
        lines.append(f"<b>Type:</b> {alert.alert_type.replace('_', ' ').title()}")
        lines.append(f"")
        
        # Token info
        lines.append(f"<b>Contract:</b> <code>{alert.token_address}</code>")
        lines.append(f"<b>Liquidity:</b> ${alert.liquidity_usd:,.0f}")
        if alert.market_cap_usd:
            lines.append(f"<b>Market Cap:</b> ${alert.market_cap_usd:,.0f}")
        lines.append(f"")
        
        # Triggered indicators
        if alert.risk_score.triggered_indicators:
            lines.append(f"<b>Triggered Indicators:</b>")
            for ind in alert.risk_score.triggered_indicators:
                emoji = cls.INDICATOR_EMOJI.get(ind, '•')
                # Find the indicator result for explanation
                ind_result = next((r for r in alert.risk_score.indicator_results if r.indicator == ind), None)
                if ind_result:
                    lines.append(f"  {emoji} {ind.replace('_', ' ').title()}: {ind_result.explanation}")
                else:
                    lines.append(f"  {emoji} {ind.replace('_', ' ').title()}")
            lines.append(f"")
        
        # Evidence summary
        if alert.evidence_summary:
            lines.append(f"<b>Key Evidence:</b>")
            for key, value in list(alert.evidence_summary.items())[:5]:
                if isinstance(value, (list, dict)):
                    value = str(value)[:100]
                lines.append(f"  • {key}: {value}")
            lines.append(f"")
        
        # Transaction links
        if alert.transaction_links:
            lines.append(f"<b>Transactions:</b>")
            for link in alert.transaction_links[:3]:
                lines.append(f"  🔗 <a href='{link}'>{link[:20]}...</a>")
            lines.append(f"")
        
        # Timestamp
        lines.append(f"<b>Detected:</b> {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"<b>Alert ID:</b> <code>{alert.alert_id}</code>")
        
        # Disclaimer
        lines.append(f"")
        lines.append(f"<i>⚠️ This is an automated risk assessment. Not financial advice. Always verify independently.</i>")
        
        return '\n'.join(lines)
    
    @classmethod
    def format_summary(cls, alerts: List[Alert]) -> str:
        """Format multiple alerts as summary"""
        if not alerts:
            return "No active alerts"
        
        lines = [f"<b>PennyShield Alert Summary</b> ({len(alerts)} alerts)"]
        lines.append(f"")
        
        for alert in alerts[:10]:
            severity_emoji = cls.SEVERITY_EMOJI.get(alert.severity, '⚪')
            chain_emoji = cls.CHAIN_EMOJI.get(alert.chain, '⚪')
            lines.append(f"{severity_emoji} {chain_emoji} <b>{alert.token_symbol}</b> - {alert.severity.upper()} - {alert.risk_score.overall_score:.1%}")
        
        return '\n'.join(lines)


# === Alert Manager ===
class AlertManager:
    """Manage alerts, deduplication, and delivery"""
    
    def __init__(self, 
                 evidence_store: EvidenceStore,
                 alert_dir: str = "/home/ubuntu/.openclaw/workspace/pennyshield/alerts"):
        self.evidence_store = evidence_store
        self.alert_dir = alert_dir
        os.makedirs(alert_dir, exist_ok=True)
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self._load_history()
    
    def _load_history(self):
        """Load alert history from disk"""
        history_path = os.path.join(self.alert_dir, "history.json")
        if os.path.exists(history_path):
            with open(history_path, 'r') as f:
                data = json.load(f)
                for item in data:
                    # Reconstruct alert (simplified)
                    pass
    
    def _save_history(self):
        """Save alert history to disk"""
        history_path = os.path.join(self.alert_dir, "history.json")
        with open(history_path, 'w') as f:
            json.dump([a.to_dict() for a in self.alert_history], f, indent=2)
    
    def create_alert(self, 
                     token_address: str,
                     chain: str,
                     token_symbol: str,
                     token_name: str,
                     risk_score: RiskScore,
                     pool_data: Dict,
                     token_data: Dict,
                     transaction_links: List[str] = None) -> Alert:
        """Create a new alert from risk assessment"""
        # Generate alert ID
        alert_id = self._generate_alert_id(token_address, chain)
        
        # Determine alert type from triggered indicators
        alert_type = self._determine_alert_type(risk_score.triggered_indicators)
        
        # Determine severity
        severity = self._determine_severity(risk_score)
        
        # Build evidence summary
        evidence_summary = self._build_evidence_summary(risk_score, pool_data, token_data)
        
        # Create alert
        alert = Alert(
            alert_id=alert_id,
            token_address=token_address,
            chain=chain,
            token_symbol=token_symbol,
            token_name=token_name,
            alert_type=alert_type,
            severity=severity,
            risk_score=risk_score,
            evidence_summary=evidence_summary,
            liquidity_usd=pool_data.get('liquidity_usd', 0),
            market_cap_usd=token_data.get('market_cap_usd'),
            transaction_links=transaction_links or []
        )
        
        # Check for duplicate (same token, similar risk within 1 hour)
        if self._is_duplicate(alert):
            return self.active_alerts.get(alert_id)
        
        # Store alert
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # Save to disk
        self._save_alert(alert)
        self._save_history()
        
        # Record in evidence store
        self.evidence_store.record_detection(
            token_address, chain, risk_score, pool_data, token_data
        )
        
        return alert
    
    def _generate_alert_id(self, token_address: str, chain: str) -> str:
        """Generate unique alert ID"""
        import hashlib
        return hashlib.sha256(
            f"{token_address}{chain}{time.time()}".encode()
        ).hexdigest()[:12]
    
    def _determine_alert_type(self, triggered_indicators: List[str]) -> str:
        """Determine alert type from triggered indicators"""
        type_priority = [
            'exit_detector',
            'liquidity_drain',
            'distribution',
            'coordinated_distribution',
            'early_snipe',
            'wallet_clustering',
            'deployer_intelligence',
            'contract_risk',
            'callout_coordination',
            'attention_anomaly',
            'popularity_reality_gap',
            'cross_launch_social',
            'deployer_link',
            'whale_activity',
            'new_pool'
        ]
        
        for t in type_priority:
            if t in triggered_indicators:
                return t
        
        return 'high_risk' if triggered_indicators else 'monitoring'
    
    def _determine_severity(self, risk_score: RiskScore) -> str:
        """Determine severity from risk score"""
        score = risk_score.overall_score
        high_risk_count = len(risk_score.triggered_indicators)
        
        if score >= 0.9 or high_risk_count >= 4:
            return 'critical'
        elif score >= 0.75 or high_risk_count >= 3:
            return 'high'
        elif score >= 0.6 or high_risk_count >= 2:
            return 'medium'
        else:
            return 'low'
    
    def _build_evidence_summary(self, risk_score: RiskScore, 
                                pool_data: Dict, token_data: Dict) -> Dict:
        """Build concise evidence summary"""
        summary = {
            'liquidity_usd': pool_data.get('liquidity_usd', 0),
            'market_cap_usd': token_data.get('market_cap_usd'),
            'holder_concentration': token_data.get('top_10_holder_pct'),
            'unique_buyers_24h': token_data.get('unique_buyers_24h'),
            'net_buy_volume_24h': token_data.get('net_buy_volume_usd_24h'),
        }
        
        # Add key indicator evidence
        for result in risk_score.indicator_results:
            if result.triggered and result.evidence:
                summary[result.indicator] = {
                    'confidence': result.confidence,
                    'explanation': result.explanation[:200],
                    'key_evidence': {k: v for k, v in list(result.evidence.items())[:3]}
                }
        
        return summary
    
    def _is_duplicate(self, alert: Alert) -> bool:
        """Check if alert is duplicate of recent alert"""
        for existing in self.active_alerts.values():
            if (existing.token_address == alert.token_address and 
                existing.chain == alert.chain and
                alert.timestamp - existing.timestamp < 3600):  # 1 hour
                return True
        return False
    
    def _save_alert(self, alert: Alert):
        """Save individual alert to disk"""
        alert_path = os.path.join(self.alert_dir, f"{alert.alert_id}.json")
        with open(alert_path, 'w') as f:
            json.dump(alert.to_dict(), f, indent=2)
    
    def acknowledge_alert(self, alert_id: str):
        """Mark alert as acknowledged"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            self._save_alert(self.active_alerts[alert_id])
    
    def set_outcome(self, alert_id: str, outcome: str, details: Dict = None):
        """Set the eventual outcome of an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].outcome = outcome
            self._save_alert(self.active_alerts[alert_id])
            self.evidence_store.record_outcome(alert_id, outcome, details)
    
    def get_active_alerts(self, chain: str = None, 
                          min_severity: str = None) -> List[Alert]:
        """Get active alerts with optional filters"""
        alerts = list(self.active_alerts.values())
        
        if chain:
            alerts = [a for a in alerts if a.chain == chain]
        
        if min_severity:
            severity_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
            min_level = severity_order.get(min_severity, 0)
            alerts = [a for a in alerts if severity_order.get(a.severity, 0) >= min_level]
        
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def cleanup_old_alerts(self, max_age_hours: int = 168):
        """Remove old acknowledged alerts from active list"""
        now = time.time()
        to_remove = []
        
        for alert_id, alert in self.active_alerts.items():
            if alert.acknowledged and (now - alert.timestamp) > max_age_hours * 3600:
                to_remove.append(alert_id)
        
        for alert_id in to_remove:
            del self.active_alerts[alert_id]


# === Telegram Delivery (placeholder - requires bot token) ===
class TelegramDelivery:
    """Deliver alerts via Telegram bot"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.bot_token and self.chat_id)
    
    def send_alert(self, alert: Alert) -> bool:
        """Send alert via Telegram"""
        if not self.enabled:
            print(f"[INFO] Telegram not configured, alert logged locally: {alert.alert_id}")
            return False
        
        try:
            import urllib.request
            message = TelegramFormatter.format_alert(alert)
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            payload = json.dumps(data).encode()
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                return result.get('ok', False)
        except Exception as e:
            print(f"[WARNING] Telegram delivery failed: {e}")
            return False
    
    def send_summary(self, alerts: List[Alert]) -> bool:
        """Send alert summary"""
        if not self.enabled:
            return False
        
        try:
            import urllib.request
            message = TelegramFormatter.format_summary(alerts)
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            payload = json.dumps(data).encode()
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                return result.get('ok', False)
        except Exception as e:
            print(f"[WARNING] Telegram summary failed: {e}")
            return False


# === Alert Rules Engine ===
class AlertRule:
    """Rule for when to send alerts"""
    
    def __init__(self, name: str, condition: callable, 
                 cooldown_hours: float = 1.0):
        self.name = name
        self.condition = condition
        self.cooldown_hours = cooldown_hours
        self.last_triggered: Dict[str, float] = {}
    
    def should_alert(self, alert: Alert) -> bool:
        """Check if alert should be sent based on rule"""
        if not self.condition(alert):
            return False
        
        key = f"{alert.token_address}_{alert.chain}"
        now = time.time()
        last = self.last_triggered.get(key, 0)
        
        if now - last < self.cooldown_hours * 3600:
            return False
        
        self.last_triggered[key] = now
        return True


# Default alert rules
DEFAULT_ALERT_RULES = [
    AlertRule(
        "critical_immediate",
        lambda a: a.severity == 'critical',
        cooldown_hours=0.5
    ),
    AlertRule(
        "high_risk_new_launch",
        lambda a: a.severity in ('high', 'critical') and a.alert_type == 'new_pool',
        cooldown_hours=1.0
    ),
    AlertRule(
        "liquidity_drain_alert",
        lambda a: 'liquidity_drain' in a.alert_type or 'exit_detector' in a.risk_score.triggered_indicators,
        cooldown_hours=2.0
    ),
    AlertRule(
        "coordinated_distribution_alert",
        lambda a: 'distribution' in a.alert_type or 'wallet_clustering' in a.risk_score.triggered_indicators,
        cooldown_hours=1.0
    ),
    AlertRule(
        "repeat_offender_alert",
        lambda a: 'deployer_link' in a.risk_score.triggered_indicators or 'cross_launch_social' in a.risk_score.triggered_indicators,
        cooldown_hours=4.0
    )
]


# === Alert Processor ===
class AlertProcessor:
    """Process risk scores and generate/deliver alerts"""
    
    def __init__(self, 
                 evidence_store: EvidenceStore,
                 delivery: TelegramDelivery = None,
                 rules: List[AlertRule] = None):
        self.alert_manager = AlertManager(evidence_store)
        self.delivery = delivery or TelegramDelivery()
        self.rules = rules or DEFAULT_ALERT_RULES
    
    def process_risk_score(self, 
                           token_address: str,
                           chain: str,
                           token_symbol: str,
                           token_name: str,
                           risk_score: RiskScore,
                           pool_data: Dict,
                           token_data: Dict,
                           transaction_links: List[str] = None) -> Optional[Alert]:
        """Process a risk score and generate alert if needed"""
        # Only alert on high risk
        if not risk_score.is_high_risk:
            return None
        
        # Create alert
        alert = self.alert_manager.create_alert(
            token_address=token_address,
            chain=chain,
            token_symbol=token_symbol,
            token_name=token_name,
            risk_score=risk_score,
            pool_data=pool_data,
            token_data=token_data,
            transaction_links=transaction_links
        )
        
        # Check rules for delivery
        for rule in self.rules:
            if rule.should_alert(alert):
                self.delivery.send_alert(alert)
                break
        
        return alert
    
    def get_alert_summary(self, chain: str = None) -> str:
        """Get formatted alert summary"""
        alerts = self.alert_manager.get_active_alerts(chain=chain, min_severity='medium')
        return TelegramFormatter.format_summary(alerts)