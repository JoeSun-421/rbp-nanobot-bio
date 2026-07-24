<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="480">

  <h1>nanobot-bio</h1>

  <p><b>RNA–RBP 结合预测 Agent</b></p>
  <p>
    输入 RNA 与 RBP，得到是否结合的判定。<br/>
    编排基于 <a href="https://github.com/HKUDS/nanobot">Nanobot</a>；结合分数来自科学工具包。
  </p>

  <p>
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/Nanobot-HKUDS%2Fnanobot-111111?logo=github" alt="Nanobot"></a>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>

  <p>
    <a href="#-原理与实现">原理与实现</a> ·
    <a href="#-克隆">克隆</a> ·
    <a href="#-安装">安装</a> ·
    <a href="#-使用">使用</a> ·
    <a href="#-你会得到什么">你会得到什么</a> ·
    <a href="#-目录">目录</a> ·
    <a href="#-更多说明">更多说明</a>
  </p>

  <p><a href="README.md">English</a> · <b>中文</b></p>
</div>

---

## 🔬 原理与实现

**科学直觉。** RNA 结合蛋白（RBP）往往通过相近的序列 motif、结构与结构域识别 RNA。若查询 RBP 与已有「会打分」的蛋白足够相近，就可以做**知识迁移**：找到相似供体、复用其预测头，再把多路证据合成一次结合判定。

**我们实现了什么。** `nanobot-bio` 把这件事做成可用的 Agent 产品：

1. **识别靶标**：判断是目录内已知 head、近同源，还是全新未见蛋白。
2. **检索供体**：用序列与结构相似度找出可借用的 RBP。
3. **借头预测**：调用科学工具包，在合适供体上得到结合分数。
4. **整合输出**：汇总为一条 JSON 结论，并附简短解释。

LLM 负责选工具、排步骤、写说明；**数值分数只来自科学工具**，不会由模型凭空编造概率。

---

## 📦 克隆

| 命令 | 含义 |
|------|------|
| `git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git` | 用 HTTPS 从 GitHub 下载本项目 |
| `cd rbp-nanobot-bio` | 进入项目目录 |

科学数据包和本项目放在**同一层**，不要放进本仓库里面：

```text
你的工作目录/
├── rbp-nanobot-bio/            ← 本项目
└── rhobind_agent_delivery/     ← 科学数据与工具
```

直连 GitHub 较慢时，可先开代理 / 镜像，再对同一 HTTPS 地址执行 `git clone`。

---

## ⚙️ 安装

| 命令 | 含义 |
|------|------|
| `bash scripts/setup_all.sh` | 创建 Python 环境、安装依赖，并接好科学工具包路径 |
| `source .venv/bin/activate` | 激活虚拟环境，之后才能直接运行 `nanobot-bio` |
| `nanobot-bio onboard` | 交互配置：选择 LLM 厂商，把 API key 存到本机 |
| `nanobot-bio doctor` | 自检：路径、registry、skill、环境是否就绪 |

需要跳过 AF3、只用 Docker，或查看完整环境变量时，打开 [`INSTALL.md`](INSTALL.md)。

---

## 🚀 使用

| 命令 | 含义 |
|------|------|
| `nanobot-bio agent --message "..."` | 一次性提问：发一句话，拿一条 JSON 结论后退出 |
| `nanobot-bio chat` | 多轮终端对话，同一套 Agent |

示例：

```bash
nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: <你的序列>"
nanobot-bio chat
```

### 对话里的斜杠命令

| 命令 | 含义 |
|------|------|
| `/help` | 查看可用斜杠命令 |
| `/status` | 查看当前模型、工具与会话 |
| `/tools` | 列出 Agent 可调用的工具 |
| `/new` | 开一个新会话 |
| `/quit` | 退出对话 |

---

## ✨ 你会得到什么

| 部分 | 作用 |
|------|------|
| **Agent** | 自动选工具、组织步骤，给出 JSON 结论 |
| **Tools** | 序列 / 结构 / 功能相关查询与预测 |
| **科学栈** | 结合分数来自 `rhobind_agent_delivery` |

常见返回字段：`label`、`confidence`、`p_hat`、`explanation`、`supporting_rbps`。

---

## 📁 目录

```text
nanobot-bio/
├── app/          命令行与应用壳
├── nanobot/      Agent runtime 与 RBP 工具
├── config/       默认配置
├── scripts/      setup_all.sh 等安装脚本
├── tests/        自动化测试
├── workspace/    Agent 工作区
└── artifacts/    本地日志与报告
```

---

## 🆘 更多说明

| 文档 | 什么时候看 |
|------|------------|
| [INSTALL.md](INSTALL.md) | 完整安装、环境变量、Docker |
| [CHANGELOG.md](CHANGELOG.md) | 各版本改了什么 |
| [RELEASE.md](RELEASE.md) | 如何发版 |

```bash
nanobot-bio doctor    # 出问题先自检
python -m pytest -q   # 静默跑自动化测试
```

---

<div align="center">

Agent runtime 来自 <a href="https://github.com/HKUDS/nanobot">HKUDS/nanobot</a>。<br/>
科学工具由 <code>rhobind_agent_delivery</code> 提供。

</div>
