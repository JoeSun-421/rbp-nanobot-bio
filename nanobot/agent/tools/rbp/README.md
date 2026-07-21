# `nanobot.agent.tools.rbp`

**English** | [中文](README.zh.md)

Curated Nanobot `Tool` implementations for RNA–RBP assessment. Classes are plugin-discoverable (`_plugin_discoverable = True`) and registered via `register_all` / delivery whitelist builders.

## Purpose

Expose a stable, LLM-facing tool surface whose numerical outputs come from delivery (or agent-local helpers such as `rna_similarity`), analogous to Transformers pipelines wrapping model calls behind typed APIs.

## Tools (summary)

| Tool | Role |
|------|------|
| `predict_interaction` | RhoBind heads |
| `get_known_rbp_list` / resolve helpers | Catalogue |
| `seq_similarity` | ESM-C neighbors |
| `rna_similarity` | RNA embedding / bank similarity (agent-local) |
| `struct_similarity` / `predict_structure` | Foldseek / AF3 |
| `get_func_annotation` / `literature_search` | Function / papers |
| `lookup_proxy_cache` / `fuse_similarity_views` | Evolve-time cache + fusion |
| Redirect stubs | Disable shell / generic web / filesystem tools |

## Editing

Edit files under this SoT directory only, then:

```bash
python -m rbp_agent.sync_overlay
```

## Constraints

- Do not invent `p_hat`; cite tool fields only.
- Structure failure ≠ similarity 0; see AF3 notes in [docs/工程指南.zh.md](../../../../docs/工程指南.zh.md) §8.

## Related

[../../../README.md](../../../README.md) · [../../../../rbp_agent/backends/delivery/](../../../../rbp_agent/backends/delivery/README.md)
