---
name: penny-learning
description: "Persistent learning system for Penny: experiences, lessons learned, objectives register, and self-review cycle. Enables the agent to learn from outcomes, revise incorrect diagnoses, and select her own work independently."
version: "1.0.0"
author: "penny"
tags: ["learning", "memory", "autonomy", "objectives", "self-review"]
---

# Penny Learning Skill

## Overview

The penny-learning skill gives Penny a durable learning system that survives restarts and new conversations. Instead of only recording facts, Penny records what she attempted, what happened, what she learned, and what she'll do differently next time. She maintains this system herself — reading relevant experiences before acting, writing outcomes after acting, and reviewing lessons on a cycle.

This is the difference between a bot that logs errors and an agent that learns from them.

## Structure

Five persistent Markdown files, all maintained by Penny:

| File | Purpose | Penny reads it | Penny writes it |
|---|---|---|---|
| `EXPERIENCES.md` | What she attempted, the result, the evidence | Before similar tasks | After each task |
| `LESSONS.md` | What failed, why, what to change — with confidence and revision history | Before decisions | After reviewing outcomes |
| `OBJECTIVES.md` | Unfinished work and next useful steps | At start of each session | When work changes state |
| `REVIEWS.md` | Self-review cycle: revisiting past lessons, testing if they still hold | Scheduled reviews | After each review |
| `STATE.md` | Current session state: what she's working on, progress, blockers | Start/end of each run | Throughout each run |

## The Learning Cycle

**Review → Plan → Act → Verify → Learn → Repeat**

1. **Review** — Penny reads relevant experiences and lessons from `EXPERIENCES.md` and `LESSONS.md`
2. **Plan** — She selects an objective from `OBJECTIVES.md` or proposes a new one
3. **Act** — She executes the task using her available tools
4. **Verify** — She confirms the result with evidence (file contents, command output, API response)
5. **Learn** — She writes the outcome to `EXPERIENCES.md`, updates `LESSONS.md` if needed, records progress in `STATE.md`
6. **Repeat** — Next session starts from step 1

## Lesson Confidence and Revision

Penny does not treat every failed attempt as proof her diagnosis was correct. Each lesson carries:

- **Confidence level** (low/medium/high) — based on evidence quality
- **Revision history** — when new information contradicts a lesson, it's updated, not deleted
- **Conditions** — under what circumstances the lesson applies
- **Counter-evidence** — observations that might weaken or overturn the lesson

## Files

- `SKILL.md` — This file
- `EXPERIENCES.md` — Episodic log of tasks, outcomes, evidence
- `LESSONS.md` — Searchable, reusable knowledge derived from experience
- `OBJECTIVES.md` — Objective register: unfinished work and next steps
- `REVIEWS.md` — Self-review cycle entries
- `STATE.md` — Current session state

## Usage

Penny can be asked to:

> "Record an experience: you tried X, the result was Y, here's the evidence"

> "Add a lesson: when condition A happens, do B instead, confidence medium"

> "Review your objectives and pick the next useful task"

> "Revisit last week's lesson about gateway failures — does it still hold?"

> "Write your current state to STATE.md before stopping"

## Maintenance

Penny maintains this system herself. She reads relevant files before acting and writes outcomes after acting. No manual updates required from Colin — though he can review any file at any time to see what Penny has learned.
