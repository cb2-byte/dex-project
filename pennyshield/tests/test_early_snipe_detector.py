import unittest

from pennyshield.shared.risk_engine import DetectionContext, WalletGraph
from pennyshield.solana.detectors import EarlySnipeDetector


class EarlySnipeDetectorTests(unittest.TestCase):
    def context(self, transactions, funding_by_wallet=None):
        graph = WalletGraph()
        for wallet, funders in (funding_by_wallet or {}).items():
            graph.add_wallet(wallet, funding_sources=list(funders))
        return DetectionContext(
            token_address="MintFixture",
            chain="solana",
            pool_data={},
            token_data={"launch_block": 100},
            transactions=transactions,
            wallet_graph=graph,
        )

    @staticmethod
    def buy(wallet, amount=100, block=100, side="buy"):
        return {
            "block": block,
            "buyer": wallet,
            "from": wallet,
            "token_amount": amount,
            "type": side,
        }

    def test_only_explicit_buys_are_counted(self):
        context = self.context([
            self.buy("wallet-buy"),
            self.buy("wallet-sell", side="sell"),
            {"block": 100, "buyer": "wallet-unknown", "token_amount": 100},
        ])
        result = EarlySnipeDetector().evaluate(context)
        self.assertFalse(result.triggered)
        self.assertEqual(result.evidence["buy_transactions"], 1)
        self.assertEqual(result.evidence["unique_buyers"], 1)

    def test_same_block_wallets_with_unrelated_funders_are_not_a_bundle(self):
        wallets = ["wallet-a", "wallet-b", "wallet-c"]
        txs = [self.buy(wallet) for wallet in wallets]
        funders = {wallet: [f"funder-{index}"] for index, wallet in enumerate(wallets)}
        result = EarlySnipeDetector().evaluate(self.context(txs, funders))
        self.assertEqual(result.evidence["bundled_groups"], [])
        self.assertEqual(result.evidence["shared_funders"], [])
        self.assertFalse(result.triggered)

    def test_bundle_tracks_each_wallet_at_each_block(self):
        txs = [
            self.buy("wallet-a", amount=100, block=100),
            self.buy("wallet-a", amount=100, block=101),
            self.buy("wallet-b", amount=100, block=101),
            self.buy("wallet-c", amount=100, block=101),
        ]
        funders = {wallet: ["shared-funder"] for wallet in ("wallet-a", "wallet-b", "wallet-c")}
        result = EarlySnipeDetector().evaluate(self.context(txs, funders))
        self.assertTrue(any(group["block"] == 101 for group in result.evidence["bundled_groups"]))
        self.assertTrue(result.triggered)

    def test_hhi_threshold_gates_two_wallet_shared_funder_signal(self):
        wallets = ["wallet-a", "wallet-b"]
        txs = [self.buy(wallet) for wallet in wallets]
        funders = {wallet: ["shared-funder"] for wallet in wallets}
        context = self.context(txs, funders)

        blocked = EarlySnipeDetector(
            concentration_threshold=0.6,
            min_bundle_wallets=3,
            min_shared_funders=2,
        ).evaluate(context)
        allowed = EarlySnipeDetector(
            concentration_threshold=0.4,
            min_bundle_wallets=3,
            min_shared_funders=2,
        ).evaluate(context)

        self.assertAlmostEqual(blocked.evidence["funder_hhi"]["shared-funder"], 0.5)
        self.assertFalse(blocked.triggered)
        self.assertTrue(allowed.triggered)


    def test_high_concentration_without_shared_funder_does_not_trigger(self):
        wallets = ["wallet-a", "wallet-b"]
        txs = [self.buy(wallet) for wallet in wallets]
        funders = {wallet: [f"independent-{index}"] for index, wallet in enumerate(wallets)}
        result = EarlySnipeDetector(
            concentration_threshold=0.4,
            min_bundle_wallets=3,
            min_shared_funders=2,
        ).evaluate(self.context(txs, funders))
        self.assertTrue(result.evidence["funder_hhi"])
        self.assertEqual(result.evidence["shared_funders"], [])
        self.assertFalse(result.triggered)

    def test_large_bundle_is_alternate_signal_but_still_requires_shared_funder(self):
        wallets = ["wallet-a", "wallet-b", "wallet-c"]
        txs = [self.buy(wallet) for wallet in wallets]
        funders = {wallet: ["shared-funder"] for wallet in wallets}
        result = EarlySnipeDetector(
            concentration_threshold=0.5,
            min_bundle_wallets=3,
            min_shared_funders=3,
        ).evaluate(self.context(txs, funders))
        self.assertLess(result.evidence["funder_hhi"]["shared-funder"], 0.5)
        self.assertEqual(len(result.evidence["bundled_groups"]), 1)
        self.assertTrue(result.triggered)


if __name__ == "__main__":
    unittest.main()
