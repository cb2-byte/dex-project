# LESSONS.md — Lessons Learned

Penny records what failed, why, and what to change next time. Each lesson carries a confidence level and revision history so she doesn't treat every failed attempt as proof her diagnosis was correct.

Format:
## <Lesson ID> — <Short description>
- **Condition:** When this lesson applies
- **Lesson:** What Penny learned (what to do or not do)
- **Confidence:** low / medium / high
- **Evidence:** What supports this lesson
- **Counter-evidence:** Observations that might weaken or overturn it
- **Revision history:** Date + what changed and why
- **Source experience:** Link to EXPERIENCES.md entry

---

## L-001 — Gateway systemd service is in failed state
- **Condition:** OpenClaw gateway systemd service is installed and enabled but stopped with state "failed"
- **Lesson:** Before assuming Penny can operate autonomously, verify the gateway service is running. If failed, investigate before running `openclaw doctor --fix` (do not run blindly).
- **Confidence:** high
- **Evidence:** `openclaw status` output shows "Gateway service: systemd user installed · enabled · stopped (state failed)"
- **Counter-evidence:** Gateway is reachable via websocket despite systemd failed state — the service state may not reflect actual runtime status
- **Revision history:** 2026-10-24: Created from Stage 1 baseline
- **Source experience:** EXPERIENCES.md entry "2026-10-24 — Stage 1 baseline inspection"

## L-002 — MEMORY.md is stale relative to current environment (CONFIRMED with direct evidence)
- **Condition:** MEMORY.md describes Mac Mini M4 in Jersey running Anthropic Claude Haiku 4.5 via clowdbot/ATXP
- **Lesson:** Do not trust MEMORY.md for current environment details (host, model, config, API keys). It describes the old clowdbot setup, not the current Oracle Ubuntu + OpenClaw environment. Always verify current state before relying on MEMORY.md.
- **Confidence:** high
- **Evidence:** MEMORY.md read directly — states "Running on Mac Mini M4", "Claude Haiku 4.5 via Anthropic API key", "clowdbot forces anthropic provider regardless of agent.json config". Current baseline shows Oracle Ubuntu, nvidia/nemotron-3.5-super-vl-120b-a12b, OpenClaw config at /home/ubuntu/.openclaw/openclaw.json
- **Counter-evidence:** None — direct file read confirms staleness
- **Revision history:** 2026-10-24: Created from Stage 1 baseline; 2026-10-24: Confirmed with direct MEMORY.md read during Phase 1 learning test
- **Source experience:** EXPERIENCES.md entries "2026-10-24 — Stage 1 baseline inspection" and "2026-10-24 — Phase 1 learning test: verify MEMORY.md staleness"

## L-003 — Skill documentation ≠ working capability (NEW — identified through independent investigation)
- **Condition:** Penny has 3 skill directories (coinbase-skill, marketing-skill, whale-sentry) each with SKILL.md describing capabilities
- **Lesson:** A SKILL.md file describing tools or features does not mean those tools exist in Penny's current inventory. Each skill must be checked against actual available tools before being treated as usable.
- **Confidence:** high
- **Evidence:** whale-sentry SKILL.md lists 7 tools (whale_sentry_start_monitoring, whale_sentry_add_wallet, whale_sentry_remove_wallet, whale_sentry_list_wallets, whale_sentry_check_now, whale_sentry_get_alerts, whale_sentry_analyze_event) — none appear in Penny's tool inventory. coinbase-skill SKILL.md explicitly states "does not automatically check balances." marketing-skill SKILL.md lists no tools at all. Confirmed by reading all 3 SKILL.md files and comparing against config tool inventory.
- **Counter-evidence:** None — direct comparison confirms the gap
- **Revision history:** 2026-10-24: Created from Phase 3 independent investigation
- **Source experience:** EXPERIENCES.md entry "2026-10-24 — Phase 3 independent investigation: skills vs actual capabilities"

## L-004 — .zip file existing ≠ usable data inside (CONFIRMED, then overturned)
- **Condition:** penny-backup.zip (22 bytes) was empty — just ZIP header, no entries
- **Lesson:** A .zip file can exist but contain no usable data. Always verify contents before assuming a backup is valid.
- **Confidence:** high
- **Evidence:** penny-backup.zip is 22 bytes, contains only ZIP end-of-central-directory record, zero entries
- **Counter-evidence:** LATER OVERTURNED — workspace.zip, skills.zip, self-improving.zip, Public.zip were all valid zips with real data
- **Revision history:** 2026-10-24: Created from penny-backup.zip failure; 2026-10-24: Overturned when workspace.zip etc. proved valid
- **Source experience:** EXPERIENCES.md entries "2026-10-24 — penny-backup.zip received (empty/invalid)" and "2026-10-24 — MAJOR BREAKTHROUGH: 4 backup zips received and extracted"

## L-005 — Live credentials exposed in recovered .env file
- **Condition:** workspace/trading-bots/.env contains live API keys and private keys (Coinbase EC private key, Bankr API key, Polytrade API key, Telegram token + chat ID)
- **Lesson:** Recovered credential files must be treated as security incidents. Rotate all exposed keys immediately. Never commit credentials to version control or leave them in unprotected workspace files.
- **Confidence:** high
- **Evidence:** .env file read directly — contains COINBASE_API_SECRET (EC private key), BANKR_API_KEY, POLYTRADE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID=868123037
- **Counter-evidence:** None
- **Revision history:** 2026-10-24: Created from workspace backup extraction
- **Source experience:** EXPERIENCES.md entry "2026-10-24 — MAJOR BREAKTHROUGH: 4 backup zips received and extracted"

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->
