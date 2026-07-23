# `scripts/`

[English](README.md) | **中文**

**nanobot-bio** 的安装与工程门禁脚本。验收逻辑在 `app.dev`（CLI：`nanobot-bio accept-golden|accept-llm|gap-closure|layout|gate`）。

| 脚本 | 作用 |
|------|------|
| `setup_all.sh` | 应用 venv、可选科学 conda、SoT sync、AF3 状态 |
| `ci_gate.sh` | 封装 → `rbp-agent gate` |
| `check_secrets.sh` | 扫描已跟踪文件中的疑似密钥 |

## `setup_all.sh`

1. 确保 `$NANOBOT_SRC` Runtime。  
2. 可选构建科学 conda。  
3. 创建 `.venv`，安装 `requirements.lock` 与 `pip install -e ".[dev]"`。  
4. 写入 `.env`、创建 `artifacts/`、同步 SoT。  
5. 可选 AF3 状态（`AF3_BUDGET_SEC`）。  
6. 默认执行 `rbp-agent doctor`。

```bash
bash scripts/setup_all.sh
source .venv/bin/activate
rbp-agent doctor && rbp-agent layout
```

不修改 delivery 源码。

## 门禁

```bash
bash scripts/ci_gate.sh
rbp-agent gate --skip-eval
bash scripts/check_secrets.sh
```

## 相关

[../README.zh.md](../README.zh.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md)
