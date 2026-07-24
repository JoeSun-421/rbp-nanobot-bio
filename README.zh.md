<div align="center">
  <img src="assets/nanobot_logo.png" alt="nanobot-bio" width="480">

  <h1>nanobot-bio</h1>

  <p><b>给定 RNA 和 RBP，判断是否结合、结合有多强。</b></p>
  <p>
    基于 <a href="https://github.com/HKUDS/nanobot">Nanobot</a> 的命令行 Agent。<br/>
    结合分数由旁边的科学工具包计算。
  </p>

  <p>
    <a href="https://github.com/HKUDS/nanobot"><img src="https://img.shields.io/badge/Nanobot-HKUDS%2Fnanobot-111111?logo=github" alt="Nanobot"></a>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/release-v0.5.1-green" alt="Release">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>

  <p>
    <a href="#这个项目做什么">这个项目做什么</a> ·
    <a href="#我们做了什么">我们做了什么</a> ·
    <a href="#快速开始">快速开始</a> ·
    <a href="#输出长什么样">输出</a> ·
    <a href="#目录">目录</a> ·
    <a href="#更多">更多</a>
  </p>

  <p><a href="README.md">English</a> · <b>中文</b></p>
</div>

---

## 这个项目做什么

RNA 结合蛋白（RBP）常常长得比较像：相似的序列、结构、结构域，往往也会识别相近的 RNA。对新来的 RBP，如果能在已有蛋白里找到邻居，就可以借用它们的预测结果，再综合成一次结合判断。

这个仓库把上述流程做成一个能直接用的 Agent：你用自然语言提问，它去检索、打分，最后给你一条结构化结论。

---

## 我们做了什么

- 提供 `nanobot-bio agent` / `chat`，用一句话或对话问 RNA–RBP 问题
- 自动找相似 RBP，并调用科学工具包 `rhobind_agent_delivery` 算结合分数
- 输出带简短说明的 JSON 结论
- 分工清楚：LLM 负责选步骤和写解释，数字来自科学工具

使用前请把科学工具包放在与本仓库**同级**的目录，不要拷进本仓库里。

---

## 快速开始

```bash
git clone https://github.com/JoeSun-421/rbp-nanobot-bio.git
cd rbp-nanobot-bio

# 期望目录：
#   上级目录/
#     rbp-nanobot-bio/
#     rhobind_agent_delivery/

bash scripts/setup_all.sh      # 建环境、装依赖
source .venv/bin/activate
nanobot-bio onboard            # 配置 LLM 与 API key
nanobot-bio doctor             # 检查路径是否正常
nanobot-bio chat               # 进入对话
# nanobot-bio agent --message "Does this RNA interact with RBP PTBP1? RNA: AUCG..."
```

对话里可用：`/help` `/status` `/tools` `/new` `/quit`

Docker、精简安装和完整环境变量见 [`INSTALL.md`](INSTALL.md)。GitHub 较慢时先开代理或镜像，再对同一 HTTPS 地址 `git clone`。

---

## 输出长什么样

结果是 JSON，常见字段：`label`、`confidence`、`p_hat`、`explanation`、`supporting_rbps`。

---

## 目录

```text
nanobot-bio/
├── app/          命令行与应用壳
├── nanobot/      Agent runtime 与 RBP 工具
├── config/       默认配置
├── scripts/      setup_all.sh
├── tests/        测试
├── workspace/    Agent 工作区
└── artifacts/    本地日志与报告
```

---

## 更多

| 文档 | 用途 |
|------|------|
| [INSTALL.md](INSTALL.md) | 完整安装、环境变量、Docker |
| [CHANGELOG.md](CHANGELOG.md) | 版本记录 |

```bash
nanobot-bio doctor    # 出问题先跑
python -m pytest -q   # 跑测试
```

---

<div align="center">

基于 <a href="https://github.com/HKUDS/nanobot">HKUDS/nanobot</a> 构建。<br/>
科学工具来自 <code>rhobind_agent_delivery</code>。

</div>
