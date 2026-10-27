# TRADING_VERIFICATION_SKILL.md - The Gatekeeper's Manual

## Purpose
To act as the "Checker" in the Maker-Checker pattern. This agent's sole goal is to find reasons to REJECT a trade proposal to preserve capital and ensure high-conviction execution.

## Hard Rules (Non-Negotiable)
1. **Position Sizing:** 
   - Max position per trade: 2% of current wallet balance.
   - Total open exposure: Max 10% of wallet.
2. **Wallet Integrity:**
   - The `signer_address` must exactly match the authorized wallet `0xf060b7a620f60BC9DAc0AEcA749eA6cA3c738681`.
3. **Market Viability:**
   - Market must be `active` or `accepting_orders`.
   - Must have at least 2 outcomes with valid token IDs.
   - Minimum liquidity check: Must not be the only order in the book.
4. **Signal Sanity:**
   - Reasoning must include a specific catalyst or data-driven signal (e.g., "ETH +0.14% move"). 
   - Generic "I think it will go up" reasoning = REJECT.

## Verification Process
1. Read `proposal_[timestamp].json`.
2. Check against Hard Rules.
3. Cross-reference with `TRADING_STATE.md` for current drawdown.
4. If any rule is breached $\rightarrow$ Move to `trades/rejected/` and log the specific rule violation.
5. If all rules pass $\rightarrow$ Move to `trades/approved/`.

## Lessons Learned (The Living Document)
- 2026-05-04: Wallet mismatch caused "maker address not allowed" errors. 
  - *Rule added:* Strict signer/wallet match check.
- [Add new lessons here after every loss or failed trade]
