# Slim vendor notes (maintainer)

In-repo `nanobot/` is the Agent Controller runtime (Proposal §6.2: SoT == runtime).
Snapshot origin: sibling `/root/autodl-tmp/bio_agent/nanobot` (metadata 0.1.0) at migrate time.

**This file does not authorize deletion.** Need an explicit chat approval before removing paths in § Remaining.

Last reviewed: 2026-07-24.

---

## What we keep under `nanobot/`

| Area | Notes |
|------|--------|
| Core | `__init__.py`, `nanobot.py`, `config_base.py`, `agent/`, `providers/`, `config/`, `sdk/`, `session/`, `bus/`, `command/`, `security/`, `utils/`, `templates/` |
| RBP SoT | `skills/rbp-agent/`, `agent/tools/rbp/` |
| Hard imports (not default-registered) | `cron/`, `apps/`, generic `agent/tools/*` kept for Config/loop lazy defaults |

**ToolLoader:** `NANOBOT_TOOL_ALLOW=rbp` by default (no shell/web/filesystem). Plugins off unless `NANOBOT_TOOL_PLUGINS=1`.

---

## Already stripped

- Product surfaces: `channels/`, `web/`, `webui/`, `cli/`, `audio/`, `bridge/`, `gateway/`, `pairing/`, `api/`, nested `setup.py` / `pyproject.toml`
- PA skills: `weather`, `tmux`, `github`, `clawhub`, `cron` (skill dir), `image-generation`, `summarize`, `update-setup`, `skill-creator` (+ `skills/README.md`)
- Repo noise: package README forest; local junk (`.coverage`, caches, `egg-info`)
- Docs converge: INSTALL = install SoT; AGENTS = short gate → `docs/工程指南.zh.md` §9

**Optional skills still present:** `long-goal`, `memory`, `my` (not required for default RBP path).

---

## Proposal checklist (migrate gates)

- [x] §3 layers: Controller=`Nanobot.run` · Toolkit=rbp tools · Predictor=delivery bridge
- [x] §6.1 providers + Tool subclasses + `skills/rbp-agent` + session + hooks
- [x] §6.2 in-repo `nanobot/skills/rbp-agent` + `nanobot/agent/tools/rbp`
- [x] §6.3 `from nanobot import Nanobot` → `from_config` → `run`
- [x] §8 lightweight: no channels/WebUI; default tools = RBP
- [x] delivery untouched; `p_hat` only from predict tools

Local smoke at migrate: `layout` OK · `pytest` 120 passed · `doctor` WARN (cgroup) · Stage-0 resolve+predict (host OOM on predict possible).

---

## Residual (do not blind-delete)

Still imported by schema/loop/context/memory — need refactor first:

`shell` / `filesystem` / `web` / `cli_apps` / `image_generation` / `message` / `self` / `file_state` / `mcp` / `apps/` / `apply_patch` / `cron` (+ `nanobot/cron/`) / image provider helpers / `session/webui_turns.py` / PA templates (`HEARTBEAT`, `SOUL`, dream, cron, …).

---

## Remaining delete candidates (new approval)

1. Sibling `bio_agent/nanobot` and `/tmp/nanobot-bio-*` backups  
2. Optional skills `long-goal` / `memory` / `my`  
3. Residual tools/templates after schema/loop decoupling  

## Must keep (product)

`nanobot/` slim + rbp SoT · `app/` · `config/` · `rbp_eval/` · `workspace/` · `tests/` · `scripts/` · `artifacts/` tree · local `docs/` · root `README` / `INSTALL` / `AGENTS` / `CHANGELOG` / `RELEASE`
