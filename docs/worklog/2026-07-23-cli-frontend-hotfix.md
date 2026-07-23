# CLI 前端紧急修复计划（2026-07-23）

## 现场故障

终端里用户粘贴多行 RNA 查询后，界面停在编辑缓冲（无 `❯`、无 Thinking、无工具行、无 Verdict）。

**根因：** `multiline=True` 时，若 buffer 已含 `\n`（粘贴），`Enter` 被绑成「插入换行」而非提交 → agent **从未启动**。Header 文案还写反了（说单行 Enter 发送、粘贴后 Esc+Enter 发送）。

## 立即修复（已做）

| 项 | 取舍 |
|----|------|
| Enter = **始终提交** | 对齐 nanobot「You:」+ Enter；粘贴后 Enter 即跑 |
| Esc+Enter / Ctrl+J = 换行 | 需要手写多行时再用 |
| 去掉 prompt 入口的 stdin flush | 避免误伤粘贴；仅在回合结束后 `flush_stdin_before_next_prompt` |
| Header 压回 3 行 | 保留 model/tools/axes/session/commands；删掉 7 行标签墙 |
| ready 一行 | 真实工具名（fuse_similarity_views 等）+ `+N` |
| 保留 | spinner-only 思考、`↳` 工具行、You 回显、footer→Verdict 沉底、TTY JSON 高亮 |

**必须重启：** `Ctrl+C` 后重新 `nanobot-bio chat`（旧进程仍持有错误 keybinding）。

---

## 附录：CLI UX 升级落地（对照 22 案例，同日）

落点：`app/core/chat_ux.py` + `app/cli.py`；回归 `tests/test_chat_ux.py`。

### P0 — 可观测 / 粘贴显示

| 项 | 实现 |
|----|------|
| 幽灵粘贴缓冲 | `PromptSession(multiline=False)` + bracketed paste（对齐 nanobot） |
| 干净 `You:` 块 | 提交后重打缩进正文，压缩空行墙；`RBP_CHAT_DEBUG=1` 才打 received 行 |
| 工具 live elapsed | `ToolLiveLine`：`↳ name` 后原地 `… running Xs` → `← name · summary · Ns` |
| LLM wait hint | Thinking 空窗 ≥2s → `waiting for LLM…` |
| 中断 | `print_interrupted` + spinner stop + `flush_stdin_before_next_prompt` |

### P1 — 输入合成器

| 项 | 实现 |
|----|------|
| Slash | `_RbpChatCompleter`：`/` 前缀 WordCompleter |
| `@file` / 路径 | PathCompleter；`expand_at_file_refs` 注入正文（截断 4k） |
| `/thinking` | off → compact → full 写进 help / header |

### P2 — Rich / expand

| 项 | 实现 |
|----|------|
| Console 门面 | `get_ux_console()` → Rich stderr（TTY / `NO_COLOR` 感知） |
| 中间 Live | `TransientAnswerLive`（非 JSON 流式句，`transient=True`，Verdict 前擦掉） |
| `/expand` | 写/读 `artifacts/sessions/last_tool.json` |

### 明确不做（仍有效）

Textual 全屏、WebUI 主路径、Live 狂刷 reasoning、科学 retrieve 确认门。

## 验收口令

```bash
# 重启 chat 后
# 1) 粘贴多行 query → Enter
# 2) 应看到对齐的 You: 块 → … running → Thinking / waiting → ↳ + running Xs → ← · Ns → ✓ → Verdict
# 3) /expand 展开上次工具；@path 注入文件
pytest tests/test_chat_ux.py -q --no-cov
nanobot-bio chat
```
