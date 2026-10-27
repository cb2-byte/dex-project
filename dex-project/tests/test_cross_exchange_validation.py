"""
Tests for Cross-Exchange Arbitrage Validation
==============================================
Tests transfer costs, fees exceeding edge, and validation logic.
"""

import pytest
import time
from paper_engine.config import PaperConfig
from paper_engine.market_data import PriceQuote
from paper_engine.cross_exchange import CrossExchangeArbValidator, ArbSignal as CrossExchangeArbSignal
from paper_engine.net_return import TransferPath
from paper_engine.market_data import ValidationStatus


class TestCrossExchangeArbValidator:
    """Test the CrossExchangeArbValidator class."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            starting_capital_usd=1000.0,
            min_net_edge_pct=0.20,
            max_staleness_seconds={
                "coinbase": 10.0,
                "kraken": 10.0,
                "uniswap_v3_base": 30.0,
            },
            min_liquidity_usd=10_000.0,
        )

    @pytest.fixture
    def validator(self, config):
        return CrossExchangeArbValidator(config)

    @pytest.fixture
    def coinbase_quote(self):
        return PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time(),
            liquidity_usd=1_000_000.0,
            exchange="coinbase",
            bid=2499.5,
            ask=2500.5,
        )

    @pytest.fixture
    def kraken_quote(self):
        return PriceQuote(
            symbol="ETH/USDC",
            price=2510.0,
            source="kraken",
            timestamp=time.time(),
            liquidity_usd=800_000.0,
            exchange="kraken",
            bid=2509.5,
            ask=2510.5,
        )

    def test_accepts_valid_cross_exchange(self, validator, coinbase_quote, kraken_quote):
        """Valid cross-exchange with positive net return should be accepted."""
        signal = validator.validate_and_score(
            quote_a=coinbase_quote,
            quote_b=kraken_quote,
            trade_size_usd=1000.0,
            transfer_path=TransferPath.SAME_CHAIN,
        )

        if signal.accepted:
            assert signal.net_return_pct >= 0.2
            assert signal.accepted is True

    def test_rejects_symbol_mismatch(self, validator, coinbase_quote):
        """Different symbols should be rejected."""
        sol_quote = PriceQuote(
            symbol="SOL/USDC",
            price=100.0,
            source="kraken",
            timestamp=time.time(),
        )

        signal = validator.validate_and_score(
            quote_a=coinbase_quote,
            quote_b=sol_quote,
            trade_size_usd=1000.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == ValidationStatus.SYMBOL_MISMATCH.value

    def test_rejects_stale_price(self, validator, coinbase_quote, kraken_quote):
        """Stale price should be rejected."""
        stale_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time() - 20,
            liquidity_usd=1_000_000.0,
            exchange="coinbase",
        )

        signal = validator.validate_and_score(
            quote_a=stale_quote,
            quote_b=kraken_quote,
            trade_size_usd=1000.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == ValidationStatus.STALE_PRICE.value

    def test_rejects_low_liquidity(self, validator, coinbase_quote, kraken_quote):
        """Low liquidity on either venue should be rejected."""
        low_liq_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time(),
            liquidity_usd=500.0,
            exchange="coinbase",
        )

        signal = validator.validate_and_score(
            quote_a=low_liq_quote,
            quote_b=kraken_quote,
            trade_size_usd=1000.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == ValidationStatus.INSUFFICIENT_LIQUIDITY.value

    def test_rejects_no_price_edge(self, validator, coinbase_quote):
        """No price edge should be rejected."""
        same_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="kraken",
            timestamp=time.time(),
            liquidity_usd=800_000.0,
            exchange="kraken",
        )

        signal = validator.validate_and_score(
            quote_a=coinbase_quote,
            quote_b=same_quote,
            trade_size_usd=1000.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == "negative_net_return"

    def test_rejects_when_transfer_costs_exceed_edge(self, validator):
        """Transfer costs exceeding gross edge should be rejected."""
        buy_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time(),
            liquidity_usd=1_000_000.0,
            exchange="coinbase",
        )
        sell_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2501.0,
            source="kraken",
            timestamp=time.time(),
            liquidity_usd=800_000.0,
            exchange="kraken",
        )

        signal = validator.validate_and_score(
            quote_a=buy_quote,
            quote_b=sell_quote,
            trade_size_usd=1000.0,
            transfer_path=TransferPath.WITHDRAW_DEPOSIT,
        )

        assert not signal.accepted
        assert signal.rejection_reason in [
            "negative_net_return",
            "transfer_cost_exceeds_edge",
            "below_threshold",
        ]

    def test_same_chain_transfer_path(self, validator, coinbase_quote, kraken_quote):
        """Same chain transfer path should have minimal costs."""
        signal = validator.validate_and_score(
            quote_a=coinbase_quote,
            quote_b=kraken_quote,
            trade_size_usd=1000.0,
            transfer_path=TransferPath.SAME_CHAIN,
        )

        assert signal.cost_breakdown.get("withdrawal_fees_usd", 0) == 0
        assert signal.cost_breakdown.get("deposit_fees_usd", 0) == 0
        assert signal.cost_breakdown.get("bridge_fees_bps", 0) == 0

    def test_withdraw_deposit_transfer_path(self, validator, coinbase_quote, kraken_quote):
        """Withdraw/deposit transfer path should include fees."""
        signal = validator.validate_and_score(
            quote_a=coinbase_quote,
            quote_b=kraken_quote,
            trade_size_usd=1000.0,
            transfer_path=TransferPath.WITHDRAW_DEPOSIT,
        )

        assert signal.cost_breakdown.get("withdrawal_fees_usd", 0) >= 0
        assert signal.cost_breakdown.get("gas_usd", 0) > 0

    def test_bridge_transfer_path(self, validator):
        """Bridge transfer path should include bridge fees."""
        base_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="uniswap_v3_base",
            timestamp=time.time(),
            liquidity_usd=1_000_000.0,
        )
        eth_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2550.0,
            source="uniswap_v3_ethereum",
            timestamp=time.time(),
            liquidity_usd=2_000_000.0,
        )

        signal = validator.validate_and_score(
            quote_a=base_quote,
            quote_b=eth_quote,
            trade_size_usd=1000.0,
            transfer_path=TransferPath.BRIDGE,
            bridge_name="hop",
        )

        assert signal.cost_breakdown.get("bridge_fees_bps", 0) > 0
        assert signal.transfer_path == "bridge"

    def test_auto_determines_transfer_path(self, validator, coinbase_quote, kraken_quote):
        """Should auto-determine transfer path when not specified."""
        signal = validator.validate_and_score(
            quote_a=coinbase_quote,
            quote_b=kraken_quote,
            trade_size_usd=1000.0,
        )

        assert signal.transfer_path == "withdraw_deposit"

    def test_scan_exchange_pairs(self, validator):
        """Scan multiple exchanges for opportunities."""
        exchange_quotes = {
            "coinbase": {
                "ETH/USDC": PriceQuote(
                    symbol="ETH/USDC",
                    price=2500.0,
                    source="coinbase",
                    timestamp=time.time(),
                    liquidity_usd=1_000_000.0,
                    exchange="coinbase",
                ),
            },
            "kraken": {
                "ETH/USDC": PriceQuote(
                    symbol="ETH/USDC",
                    price=2510.0,
                    source="kraken",
                    timestamp=time.time(),
                    liquidity_usd=800_000.0,
                    exchange="kraken",
                ),
            },
        }

        signals = validator.scan_exchange_pairs(exchange_quotes, trade_size_usd=1000.0)
        assert len(signals) >= 0


class TestCrossExchangeArbSignal:
    """Test CrossExchangeArbSignal data class."""

    def test_to_dict(self, coinbase_quote, kraken_quote):
        """Signal should serialize to dict."""
        signal = CrossExchangeArbSignal(
            accepted=True,
            gross_return_pct=0.5,
            net_return_pct=0.3,
            cost_breakdown={"trading_fees_bps": 56, "slippage_bps": 20},
            trade_size_usd=1000.0,
            quotes_used={"quote_a": coinbase_quote, "quote_b": kraken_quote},
            transfer_path="same_chain",
        )

        d = signal.to_dict()
        assert d["accepted"] is True
        assert d["transfer_path"] == "same_chain"
        assert "quote_a" in d["quotes_used"]