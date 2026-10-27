# EXPERIENCES.md — Episodic Memory Log

Penny records what she attempted, the result, and the evidence. Each entry is a task she executed and its outcome.

Format:
## <YYYY-MM-DD> — <Task description>
- **Attempted:** What Penny tried to do
- **Result:** Success / failure / partial / unknown
- **Evidence:** File contents, command output, API response, or observation
- **Lesson reference:** Link to LESSONS.md entry if one was created or updated
- **Next steps:** What should happen next, if anything

---

## 2026-10-24 — Stage 1 baseline inspection of Penny's OpenClaw environment
- **Attempted:** Inspect Penny's current OpenClaw environment — gateway status, workspace access, memory files, execution capability, Telegram channel, scheduler/automations
- **Result:** Success (partial — scheduler not confirmed)
- **Evidence:** `openclaw status` output; workspace listing (48 entries); config read; file write/read test (`penny-task-test.txt`); Telegram channel ON/OK
- **Key findings:**
  - Gateway reachable at ws://127.0.0.1:18789 (73ms response)
  - Workspace fully readable/writable: AGENTS.md, MEMORY.md, IDENTITY.md, USER.md, SOUL.md, dex-project/, pennyshield/, skills/, recovered/
  - 15+ daily memory files present (Oct 2–23)
  - File execution + verification proven (wrote and read back test file)
  - Telegram channel ON with token configured
  - Gateway systemd service: stopped/failed state
  - No backups recorded
  - Scheduler/automations: not confirmed (automations tool not found; openclaw tool returned inference error)
  - IDENTITY.md and USER.md: empty templates
  - MEMORY.md: describes old Mac Mini M4 + Anthropic Haiku 4.5 via clowdbot/ATXP, NOT current Oracle Ubuntu environment
- **Lesson reference:** L-001 (Gateway systemd service failed state); L-002 (MEMORY.md is stale)
- **Next steps:** Repair gateway service via `openclaw doctor --fix`; confirm scheduler availability; build learning system (this skill)

## 2026-10-24 — Phase 1 learning test: verify MEMORY.md staleness
- **Attempted:** Read MEMORY.md to confirm whether it describes the current environment or an old one
- **Result:** Success — MEMORY.md confirmed stale
- **Evidence:** MEMORY.md explicitly states "Running on Mac Mini M4 in Jersey, Channel Islands", "Currently: Claude Haiku 4.5 via Anthropic API key", "Not on Ollama yet — despite hours of trying, OpenClaw/clowdbot ignores config changes". Current environment is Oracle Ubuntu (7.0.0-1012-oracle arm64), model nvidia/nemotron-3.5-super-vl-120b-a12b, OpenClaw config at /home/ubuntu/.openclaw/openclaw.json
- **Lesson reference:** L-002 confirmed with direct file evidence
- **Next steps:** Start Phase 2 task that benefits from L-002 (don't trust MEMORY.md for current environment details)

## 2026-10-24 — Phase 2 learning test: apply L-002 (verify current environment independently)
- **Attempted:** Verify the actual current environment independently instead of trusting MEMORY.md, applying lesson L-002
- **Result:** Success — confirmed Oracle Ubuntu 24.04.5 LTS, model nvidia/nemotron-3.5-super-vl-120b-a12b, config at /home/ubuntu/.openclaw/openclaw.json
- **Evidence:** `uname -a` → Linux openclaw 7.0.0-1012-oracle #12~24.04.1-Ubuntu SMP PREEMPT Mon Sep 14 05:33:27 UTC 2026 aarch64; `cat /etc/os-release` → Ubuntu 24.04.5 LTS; session context shows model nvidia/nemotron-3.5-super-vl-120b-a12b; `ls /home/ubuntu/.openclaw/openclaw.json` confirms config exists
- **Lesson applied:** L-002 (don't trust MEMORY.md for current environment details) — I independently verified host, model, and config path instead of relying on MEMORY.md's Mac Mini M4 + Anthropic claims
- **Lesson reference:** L-002
- **Next steps:** Record Phase 3 verification that the lesson influenced the decision

## 2026-10-24 — Phase 3 independent investigation: skills vs actual capabilities
- **Attempted:** Investigate whether Penny's existing skills match her actual capabilities, identifying inconsistencies without being told which lesson to apply
- **Result:** Success — inconsistencies identified in all 3 skills
- **Evidence:**
  - whale-sentry SKILL.md claims 7 tools: whale_sentry_start_monitoring, whale_sentry_add_wallet, whale_sentry_remove_wallet, whale_sentry_list_wallets, whale_sentry_check_now, whale_sentry_get_alerts, whale_sentry_analyze_event. None of these appear in Penny's current tool inventory. Skill says "Once configured and installed" — it has not been installed via `openclaw skills install`.
  - coinbase-skill SKILL.md explicitly states "does not automatically check balances" and "actual API calls must be implemented per Coinbase's specifications." No coinbase tools in inventory.
  - marketing-skill SKILL.md describes copywriting steps (headlines, body copy, CTA, platform optimization) but lists no tools — it's a guidance document, not an executable skill.
  - Available tools confirmed: exec (full mode, safe bins: find, ls, curl, grep, sed, awk, cat, head, tail, wc, date, ps, df, free, uptime), plugins: apple-fm, browser, duckduckgo, nvidia, ollama, telegram, xai
- **Confirmed facts:** 3 skill directories exist; whale-sentry claims 7 tools not in inventory; coinbase-skill is explicitly non-functional for auto-balance; marketing-skill has no tools
- **Hypotheses (not confirmed):** whale-sentry tools might exist if installed via `openclaw skills install whale-sentry` (not attempted); coinbase .env file referenced at /home/ubuntu/.openclaw/workspace/fly_deploy/trading-bots/.env exists but not checked
- **Lesson reference:** L-003 (new — skill documentation ≠ working capability)
- **Next steps:** Record L-003 as a lesson; decide whether to investigate coinbase .env file or attempt whale-sentry installation

## 2026-10-24 — penny-backup.zip received (empty/invalid)
- **Attempted:** Examine penny-backup.zip uploaded by Colin for Penny's recovered files
- **Result:** Failure — file is empty/invalid
- **Evidence:** File size is 22 bytes. Contents are just ZIP end-of-central-directory record (PK\x05\x06...) with zero entries. No actual backup data present.
- **Conclusion:** Not a usable backup. Either not compressed properly, created empty, or upload was truncated.
- **Lesson reference:** L-003 (skill documentation ≠ working capability) — a .zip file existing doesn't mean it contains usable data, just as a SKILL.md describing tools doesn't mean those tools exist
- **Next steps:** Ask Colin for another backup or alternative file transfer method; continue with Telegram uploads for critical files; pursue MacBook node pairing for bulk transfer

## 2026-10-24 — MAJOR BREAKTHROUGH: 4 backup zips received and extracted
- **Attempted:** Receive and extract Colin's backup zips: Public.zip, self-improving.zip, skills.zip, workspace.zip
- **Result:** Success — all 4 zips are real and extracted
- **Evidence:**
  - workspace.zip (75,022 bytes, 35 files): trading-bots/.env (live Coinbase API key + EC private key, Bankr API key, Polytrade API key, Telegram token + chat ID 868123037), trading-bots/config.json (all wallets: Bankr, Polymarket, Bitcoin, XRP, Monero; safety limits £100 max; dry_run:true), trading-bots/README.md (setup instructions), trading-bot-backtest/ (backtesting scripts), task_state.json (2026-03-30), daily_loss.json (2026-07-27, £0 loss)
  - self-improving.zip (1,720 bytes, 4 files): corrections.md (empty), memory.md (hot tier, empty), index.md (memory index)
  - skills.zip (1,967 bytes, 4 files): sonoscli skill (Sonos speaker control)
  - Public.zip (1,929 bytes, 3 files): minimal (.DS_Store files only)
- **SECURITY ALERT:** Live credentials now in Penny's workspace on Ubuntu server:
  - Coinbase API key + EC private key (.env)
  - Bankr API key (.env)
  - Polytrade API key (.env)
  - Telegram bot token + chat ID (.env)
- **Lesson reference:** L-003 (zip file ≠ usable data) — this time the zips WERE usable
- **Next steps:** Rotate exposed credentials (kept per Colin's instruction); review all recovered files; continue MacBook node pairing for remaining SSD files

## 2026-10-24 — Full implementation: apply last-good config + copy all recovered files
- **Attempted:** Implement everything: apply last-good OpenClaw config, copy workspace files, memory files, skills, sonoscli skill
- **Result:** Success — all implemented
- **Evidence:**
  - Backed up current config as openclaw.json.backup-before-implementation-2026-10-24
  - Applied openclaw.json.last-good to /home/ubuntu/.openclaw/openclaw.json
  - Copied trading-bots/ and trading-bot-backtest/ to workspace/ (14 files)
  - Copied 50 daily memory files + .dreams/ + heartbeat-state.json to workspace/memory/
  - Copied sonoscli skill to workspace/skills/
  - Copied 164 skill directories from skills-v2.zip to workspace/skills/
- **Lesson reference:** L-007 (gateway bind changed to "lan"), L-005 (credential exposure — kept per Colin's instruction)
- **Next steps:** Restart gateway to apply config changes; pair MacBook node for remaining SSD files

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->

<!-- project: path:/home/ubuntu/.openclaw/workspace/skills/penny-learning -->
