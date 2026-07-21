# `tests/`

[English](README.md) | **中文**

Pytest 覆盖导入、mapping 一致性、onboard/device、own-head 逻辑、verdict 解包、布局合规、评测指标、自演进、RNA similarity mock 与 chat UX。默认不要求重 GPU delivery 任务（对应 Transformers / PyTorch 单元与集成测试分层）。

## 运行

```bash
source .venv/bin/activate
pytest -q
rbp-agent gate --skip-eval
```

覆盖率门槛见 `pyproject.toml`（30%）。

## 代表用例

| 模块 | 焦点 |
|------|------|
| `test_skeleton_imports.py` | 导入烟测 |
| `test_mapping_sync.py` | mapping ↔ 白名单 |
| `test_self_evolution.py` / `test_evolve_eval.py` | 演进与 nested-split |
| `test_rna_similarity.py` | RNA 工具 mock |
| `test_gate_report_schema.py` | 报告 schema |

主机级验收：`rbp-agent layout|doctor|own-head|mvp`，见 [../docs/工程指南.zh.md](../docs/工程指南.zh.md) §6。

## 相关

[../README.zh.md](../README.zh.md)
