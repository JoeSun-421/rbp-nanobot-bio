<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="480">

  <h1>nanobot-bio</h1>

  <p><b>Predict whether an RNA binds an RBP — and how strongly.</b></p>
  <p>
    An agent built on <a href="https://github.com/HKUDS/nanobot">Nanobot</a>.<br/>
    Binding scores come from a separate science tool bundle.
  </p>

  <p>
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/Nanobot-HKUDS%2Fnanobot-111111?logo=github" alt="Nanobot"></a>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>

  <p>
    <a href="#about">About</a> ·
    <a href="#what-we-built">What we built</a> ·
    <a href="#get-started">Get started</a> ·
    <a href="#output">Output</a> ·
    <a href="#layout">Layout</a> ·
    <a href="#more">More</a>
  </p>

  <p><b>English</b> · <a href="README.zh.md">中文</a></p>
</div>

---

## About

RNA-binding proteins (RBPs) often share related sequence and structure patterns. When a new RBP looks like ones we already know how to score, we can find those neighbors, reuse their predictors, and combine the evidence into one binding call.

`nanobot-bio` turns that idea into a small command-line agent: you ask in natural language, it runs the retrieval and scoring tools, and it returns a structured answer.

---

## What we built

- A chat / one-shot CLI (`nanobot-bio agent`, `nanobot-bio chat`) for RNA–RBP questions
- Automatic lookup of similar RBPs and binding scores from the science tool bundle (`rhobind_agent_delivery`)
- A JSON verdict with a short explanation
- Clear split: the LLM plans and explains; numbers come from the science tools

You need the science bundle as a **sibling** directory of this repo (not inside it).

---

## Get started

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio

# expected layout:
#   parent/
#     rbp-nanobot-bio/
#     rhobind_agent_delivery/

bash scripts/setup_all.sh      # create env and install deps
source .venv/bin/activate
nanobot-bio onboard            # choose LLM provider + API key
nanobot-bio doctor             # check that paths look sane
nanobot-bio chat               # interactive
# nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: AUCG..."
```

In chat: `/help` `/status` `/tools` `/new` `/quit`

Docker, lighter installs, and the full environment list live in [`INSTALL.md`](INSTALL.md).

---

## Output

Answers are JSON. Typical fields: `label`, `confidence`, `p_hat`, `explanation`, `supporting_rbps`.

---

## Layout

```text
nanobot-bio/
├── app/          CLI and app shell
├── nanobot/      Agent runtime and RBP tools
├── config/       Defaults
├── scripts/      setup_all.sh
├── tests/        Tests
├── workspace/    Agent workspace
└── artifacts/    Local logs and reports
```

---

## More

| Doc | Use it for |
|-----|------------|
| [INSTALL.md](INSTALL.md) | Full setup, env vars, Docker |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

```bash
nanobot-bio doctor    # first check when something fails
python -m pytest -q   # run tests
```

---

<div align="center">

Built with <a href="https://github.com/HKUDS/nanobot">HKUDS/nanobot</a>.<br/>
Science tools from <code>rhobind_agent_delivery</code>.

</div>
