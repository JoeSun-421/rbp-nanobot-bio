# nanobot-bio

RNA–RBP interaction **agent**: nested [nanobot](nanobot/) + read-only
[`rhobind_agent_delivery`](../rhobind_agent_delivery/).

## Layout (proposal §6.2)

```text
nanobot-bio/
  nanobot/                 # framework + skills/rbp-agent + agent/tools/rbp
  backends/delivery/       # delivery tool client (read-only science bridge)
  integrate.py             # RBPAgent → Nanobot.from_config().run
  rbp_eval/                # traces + self-evolution
  cli.py                   # rbp-agent entry
  core/                    # onboard / chat UX / verdict schema only
```

## Setup

```bash
export BIO_ROOT=/path/to/bio_agent
source $BIO_ROOT/nanobot-bio/scripts/activate_env.sh
pip install -e $BIO_ROOT/nanobot-bio
rbp-agent onboard
rbp-agent doctor
```

Science envs (conda): delivery `agent/setup_envs.sh`
(`protein_embed` / `rna` / `rhobind`; AF3 optional). Prefer ≥8–16 GiB RAM for RhoBind.

## Behaviour

- **Stage 0 (in-catalogue RBP):** `resolve_rbp` → own-head `predict_interaction` once → JSON → **stop**
- **Unseen RBP:** retrieve → donor `predict_interaction` → integrate → JSON
- Product path is `Nanobot.run` only (fixed `core/pipeline` removed)
- Never invent `p_hat`. On predict OOM/timeout: `p_hat=null`, do not retry
- Never commit API keys

## Acceptance / E2E (ideal science env)

Golden science numbers live in delivery
[`agent/examples/README.md`](../rhobind_agent_delivery/agent/examples/README.md)
(own-head ≈ **0.966**, AUPRC 0.9311).

```bash
# Case 1 — own-head (no LLM)
rbp-agent own-head
# PASS: prob ≈ 0.966 ± 0.05

# Case 1 — via Nanobot agent
rbp-agent agent --example pos --strict
# JSON: label=Strong, p_hat≈0.966; tools: resolve_rbp → predict_interaction → STOP

rbp-agent chat
```

```bash
# Case 2 — unseen / force transfer
rbp-agent agent --message "..." --force-transfer
```

```bash
# Case 3 — delivery factory smoke (no nanobot)
bash $DELIVERY_ROOT/agent/examples/run_example.sh cpu
```
