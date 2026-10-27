"""
Analysis module for Whale Sentry - NVIDIA Nemotron analysis integration.
"""
import json
from typing import Dict, List, Optional
import aiohttp


class NVIDIAAnalyzer:
    """Analyze on-chain events using NVIDIA Nemotron API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://integrate.api.nvidia.com/v1/chat/completions"
        self.session = None

    async def __aenter__(self):
        import aiohttp
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def analyze_transaction(self, alert: Dict) -> str:
        """Analyze a whale transaction and provide insights."""
        prompt = self._build_analysis_prompt(alert)
        return await self._call_nvidia(prompt)

    async def analyze_wallet_behavior(self, wallet_address: str, chain: str, 
                                       recent_txs: List[Dict], wallet_label: str) -> str:
        """Analyze overall wallet behavior patterns."""
        prompt = self._build_wallet_analysis_prompt(wallet_address, chain, recent_txs, wallet_label)
        return await self._call_nvidia(prompt)

    async def analyze_market_impact(self, alert: Dict, related_events: List[Dict]) -> str:
        """Analyze potential market impact of a whale move."""
        prompt = self._build_market_impact_prompt(alert, related_events)
        return await self._call_nvidia(prompt)

    def _build_analysis_prompt(self, alert: Dict) -> str:
        """Build prompt for single transaction analysis."""
        chain = alert.get("chain_name", alert.get("chain", "Unknown"))
        value = alert.get("value_usd", alert.get("value", 0))
        value_str = f"${alert.get('value_usd', 0):,.2f}" if alert.get("value_usd") else f"{alert.get('value', 0)} native"
        
        from_addr = alert.get("from_address", "")[:8] + "..." + alert.get("from_address", "")[-6:]
        to_addr = alert.get("to_address", "")[:8] + "..." + alert.get("to_address", "")[-6:]
        wallet_label = alert.get("wallet_label", "Unknown")
        chain_name = alert.get("chain_name", alert.get("chain", "Unknown"))
        
        token_info = ""
        if alert.get("token_symbol"):
            token_info = f"Token: {alert['token_symbol']} ({alert.get('token_value', 0):,.4f})"
        else:
            token_info = f"Native: {alert.get('value', 0)} {alert.get('chain', 'ETH')}"

        prompt = f"""You are an expert on-chain analyst. Analyze this whale transaction:

**Transaction Details:**
- Chain: {chain_name}
- Wallet: {alert.get('wallet_label', 'Unknown')} ({alert.get('wallet_address', '')[:8]}...{alert.get('wallet_address', '')[-6:]})
- From: {alert.get('from_address', '')[:8]}...{alert.get('from_address', '')[-6:]}
- To: {alert.get('to_address', '')[:8]}...{alert.get('to_address', '')[-6:]}
- Value: {alert.get('value_usd', 0):,.2f} USD / {alert.get('value', 0)} native
- Token: {alert.get('token_symbol', 'Native')} ({alert.get('token_value', 0):,.4f})
- Chain: {alert.get('chain_name', 'Unknown')}
- Tx Hash: {alert.get('hash', '')[:16]}...

**Context:**
- Wallet Label: {alert.get('wallet_label', 'Unknown')}
- Threshold Triggered: {alert.get('threshold_triggered', 'N/A')}
- Chain: {alert.get('chain', 'Unknown')}

Provide a concise analysis (2-3 sentences) covering:
1. What type of activity this likely represents (accumulation, distribution, exchange deposit/withdrawal, DeFi interaction, etc.)
2. Potential market impact or signal
3. Any notable patterns or concerns

Be concise, professional, and actionable. No fluff."""

        return prompt

    def _build_wallet_analysis_prompt(self, wallet_address: str, chain: str, 
                                       recent_txs: List[Dict], wallet_label: str) -> str:
        """Build prompt for wallet behavior analysis."""
        tx_summary = []
        for tx in recent_txs[:10]:
            direction = "OUT" if tx.get("from_address", "").lower() == wallet_address.lower() else "IN"
            value = tx.get("value_usd", tx.get("value", 0))
            chain_name = tx.get("chain_name", "Unknown")
            token = tx.get("token_symbol", "Native")
            value_str = f"${tx.get('value_usd', 0):,.2f}" if tx.get("value_usd") else f"{tx.get('value', 0)} {tx.get('token_symbol', 'Native')}"
            tx_summary.append(f"  - {direction} {value_str} {token} on {chain_name}")

        tx_text = "\n".join(tx_summary) if tx_summary else "No recent transactions"

        prompt = f"""You are an expert on-chain analyst. Analyze this wallet's recent behavior:

**Wallet:** {wallet_label} ({wallet_address[:8]}...{wallet_address[-6:]})
**Chain:** {chain}
**Recent Transactions (last 10):**
{chr(10).join(f"  - {tx}" for tx in tx_summary)}

Analyze the wallet's behavior pattern:
1. Accumulation vs distribution trend
2. Exchange interaction patterns (deposits/withdrawals)
3. DeFi protocol usage
4. Risk level (low/medium/high)
4. Notable patterns or anomalies

Provide 3-4 concise sentences. Be specific about what the wallet is likely doing."""

        return prompt

    def _build_market_impact_prompt(self, alert: Dict, related_events: List[Dict]) -> str:
        """Build prompt for market impact analysis."""
        value_usd = alert.get("value_usd", 0)
        chain = alert.get("chain_name", "Unknown")
        
        related_text = ""
        if related_events:
            for ev in related_events[:5]:
                related_text += f"  - {ev.get('chain_name', '?')}: ${ev.get('value_usd', 0):,.2f} {ev.get('token_symbol', 'Native')} ({ev.get('alert_type', 'transfer')})\n"
        else:
            related_text = "  No related events detected."

        prompt = f"""You are a crypto market analyst. Assess the market impact of this whale move:

**Primary Alert:**
- Chain: {alert.get('chain_name', 'Unknown')}
- Value: ${alert.get('value_usd', 0):,.2f}
- Token: {alert.get('token_symbol', 'Native')}
- From: {alert.get('from_address', '')[:8]}...{alert.get('from_address', '')[-6:]}
- To: {alert.get('to_address', '')[:8]}...{alert.get('to_address', '')[-6:]}
- Wallet: {alert.get('wallet_label', 'Unknown')}

**Related Recent Events:**
{related_text}

Assess:
1. Immediate market impact (price slippage, liquidity drain)
2. Sentiment signal (bullish/bearish/neutral)
3. Potential follow-on effects
4. Time horizon for impact

Provide 3-4 concise sentences. Focus on actionable insight for traders."""

        return prompt

    async def _call_nvidia(self, prompt: str) -> str:
        """Call NVIDIA Nemotron API."""
        if not self.session:
            import aiohttp
            self.session = aiohttp.ClientSession()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "nvidia/nemotron-3-ultra-550b-a55b",  # or nemotron-3-ultra
            "messages": [
                {"role": "system", "content": "You are an expert crypto on-chain analyst. Provide concise, actionable analysis."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 512,
            "top_p": 0.9,
        }

        try:
            async with self.session.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "Analysis unavailable")
                else:
                    error_text = await resp.text()
                    return f"Analysis failed (HTTP {resp.status}): {error_text[:200]}"
        except Exception as e:
            return f"Analysis error: {str(e)[:200]}"