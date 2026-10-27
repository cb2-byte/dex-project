# OBJECTIVES.md — Objective Register

Penny's unfinished work and next useful steps. She reads this at the start of each session to choose what to work on, and updates it when work changes state.

Format:
## <Objective ID> — <Short title>
- **Status:** proposed / in-progress / blocked / completed / abandoned
- **Priority:** low / medium / high
- **Description:** What the objective is and why it matters
- **Next step:** The concrete next action Penny should take
- **Blockers:** What's preventing progress, if anything
- **Related experiences:** Links to EXPERIENCES.md entries
- **Related lessons:** Links to LESSONS.md entries
- **Created:** <YYYY-MM-DD>
- **Updated:** <YYYY-MM-DD>

---

## OBJ-001 — Repair OpenClaw gateway systemd service
- **Status:** proposed
- **Priority:** high
- **Description:** Gateway service is in failed state. Needs `openclaw doctor --fix` and restart to ensure reliable operation.
- **Next step:** Run `openclaw doctor --fix` against the same state/config, then restart the gateway.
- **Blockers:** None identified
- **Related experiences:** EXPERIENCES.md "2026-10-24 — Stage 1 baseline inspection"
- **Related lessons:** L-001 (Gateway systemd service failed state)
- **Created:** 2026-10-24
- **Updated:** 2026-10-24

## OBJ-002 — Update MEMORY.md to reflect current Oracle Ubuntu environment
- **Status:** proposed
- **Priority:** medium
- **Description:** MEMORY.md describes old Mac Mini M4 + Anthropic setup. Needs updating to current Oracle Ubuntu + OpenClaw config.
- **Next step:** Edit MEMORY.md with current environment details (host, model, config path, workspace path).
- **Blockers:** None identified
- **Related experiences:** EXPERIENCES.md "2026-10-24 — Stage 1 baseline inspection"
- **Related lessons:** L-002 (MEMORY.md is stale)
- **Created:** 2026-10-24
- **Updated:** 2026-10-24

## OBJ-003 — Confirm scheduler/automations availability
- **Status:** proposed
- **Priority:** medium
- **Description:** Cannot confirm if Penny can initiate work without a message from Colin. automations tool not found; openclaw tool returned inference error when queried.
- **Next step:** Retry automations check; investigate scheduler configuration.
- **Blockers:** openclaw tool inference error; automations tool not available
- **Related experiences:** EXPERIENCES.md "2026-10-24 — Stage 1 baseline inspection"
- **Created:** 2026-10-24
- **Updated:** 2026-10-24

## OBJ-004 — Fill IDENTITY.md and USER.md
- **Status:** proposed
- **Priority:** low
- **Description:** Both files are empty templates. Colin should fill these in, or Penny can propose drafts for his review.
- **Next step:** Ask Colin for his name, preferred name, timezone, and Penny's desired identity details.
- **Blockers:** Requires Colin input
- **Created:** 2026-10-24
- **Updated:** 2026-10-24

## OBJ-005 — Prepare for Digital Futures Data Engineering interview
- **Status:** proposed
- **Priority:** high
- **Description:** Interview with Reece Gerard on Tuesday 27 October 2026, 16:00–16:20 UTC via Microsoft Teams. Role: Data Engineering.
- **Next step:** Ask Colin what preparation he wants — Python practice, AWS concepts, data engineering fundamentals, interview talking points, or mock questions.
- **Blockers:** None — can start immediately
- **Related experiences:** EXPERIENCES.md entry "2026-10-24 — Phase 3 independent investigation: skills vs actual capabilities" (Penny confirmed she can read files and investigate)
- **Created:** 2026-10-24
- **Updated:** 2026-10-24

## OBJ-006 — Rotate exposed credentials from recovered .env file
- **Status:** proposed
- **Priority:** critical
- **Description:** workspace/trading-bots/.env contains live Coinbase API key + EC private key, Bankr API key, Polytrade API key, Telegram token + chat ID. These are now on the Ubuntu server and must be rotated.
- **Next step:** Colin rotates Coinbase, Bankr, Polytrade API keys and Telegram bot token. Penny will NOT use these credentials.
- **Blockers:** Requires Colin action on external platforms
- **Related experiences:** EXPERIENCES.md entry "2026-10-24 — MAJOR BREAKTHROUGH: 4 backup zips received and extracted"
- **Created:** 2026-10-24
- **Updated:** 2026-10-24

## OBJ-007 — Review and place recovered backup files in workspace
- **Status:** proposed
- **Priority:** high
- **Description:** 4 backup zips extracted (workspace.zip, skills.zip, self-improving.zip, Public.zip). Need to review all files and decide where each belongs in Penny's workspace.
- **Next step:** Review remaining extracted files (trading bot scripts, backtest data, etc.) and place them appropriately.
- **Blockers:** None
- **Related experiences:** EXPERIENCES.md entry "2026-10-24 — MAJOR BREAKTHROUGH: 4 backup zips received and extracted"
- **Created:** 2026-10-24
- **Updated:** 2026-10-24

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->
