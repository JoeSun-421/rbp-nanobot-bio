# `rbp_eval`

[English](README.md) | **中文**

**nanobot-bio** 的评测与离线自演进包：light LOO transfer 查询、evaluation-plan 消融、多视图融合、proxy cache、Nanobot 追踪钩子，以及 nested-split evolve 评测。

## 目的

在不修改 delivery 的前提下量化检索–迁移策略。轻量协议将 *评测 harness* 与 *科学内核* 分离，做法上接近 Scanpy 指标模块、Transformers evaluate、DSPy 离线编译循环等成熟工具。

## 模块

| 模块 | 作用 |
|------|------|
| `loo_eval.py` | Light LOO → `eval_loo_report.*` |
| `evaluation_plan.py` | held-out、AUROC/AUPRC、消融、strata、faithfulness 表 |
| `evolve_eval.py` | medoid 半集；defaults vs retuned |
| `runner.py` | evolve 用 val batch hit lists |
| `evaluator.py` | 归因、权重/abstain/标签调参、toolkit 提案、cache 晋升 |
| `fuse_hits.py` | 多视图融合 |
| `proxy_cache.py` | `proxy_map.json` |
| hooks / `trace_schema.py` | 结构化 traces |

## 入口

```bash
rbp-agent eval-plan
rbp-agent evolve [--with-esm] [--with-labels PATH]
rbp-agent evolve-eval [--tier-a-ok true]
python -m rbp_eval.loo_eval
python -m rbp_eval.evaluation_plan
python -m rbp_eval.evolve_eval
```

## 产出

| 产物 | 内容 |
|------|------|
| `eval_loo_report.*` | policy vs own-head |
| `evaluation_plan_report.*` | 消融与主指标 |
| `evolve_eval_report.*` | `delta_auprc` 与晋升建议 |
| `self_evolution_report.json` | evolve 全量报告 |
| `proxy_map.json` | Stage-1 旁路缓存 |

## 限制

- Light LOO 为 CSV 查询；全量 FASTA 重算延期。
- 标签 CE 需 `{p_hat, y}`。
- Nested split 降低但不消除同矩阵乐观偏差。

## 相关

[../README.zh.md](../README.zh.md) · [../docs/工程指南.zh.md](../docs/工程指南.zh.md) §4.5–§6
