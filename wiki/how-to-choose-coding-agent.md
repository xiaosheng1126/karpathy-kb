---
schema_version: "1"
status: draft
tags: [coding-agent, ai-tools, decision, terminal, ide]
sources: []
created_at: 2026-06-24
updated_at: 2026-06-24
last_verified_at: 2026-06-24
valid_until: 2026-12
---

# 如何选择 Coding Agent

## 结论

**当前默认组合（2026-06）**：

- **终端 / 后台长任务**：Codex CLI（已用，免费额度内）
- **复杂重构 / 跨文件改动**：Claude Code（刚 star，待实测）
- **快速浏览代码 / GUI 交互**：Cursor 或 Qoder（已用，按场景切换）
- **多 agent 编排 / harness 性能优化**：观察 ECC，未投入生产

不要追求"一个工具吃所有场景"。当前阶段（2026-06）三种工具能力差异明显，选错会浪费 token 和时间。

## 适用场景

这篇 wiki 服务的决策场景：

- 接到一个新任务，不确定用哪个 agent 起手
- 同事/朋友推荐某个新 agent，要不要跟进
- 想做 agent 之间的能力对比，避免重复试错
- 评估"是否值得迁移到新工具"

## 判断依据

**判断**：Coding agent 当前没有"通吃赢家"，要按任务形态切换。
- 置信度：high
- 有效期：2026-12
- 来源：[待补 raw，基于亲身使用]
- 不确定性：模型快速迭代，每 3-6 个月需重新评估

**判断**：Codex CLI 适合"在终端里跑、需要看完整输出、不需要 UI"的任务。
- 置信度：medium
- 有效期：2026-12
- 来源：[待补 raw]
- 不确定性：尚未与 Claude Code 做严格对照

**判断**：Claude Code 在长上下文复杂重构上比 Codex 强（社区共识）。
- 置信度：medium
- 有效期：2026-09
- 来源：[待补 raw - 需自测]
- 不确定性：尚未自测，仅基于二手评价；需要跑一次同任务对比

**判断**：Cursor / Qoder 类 GUI agent 适合"探索代码 + 边看边改"的工作流，不适合脚本化和长任务。
- 置信度：high
- 有效期：2026-12
- 来源：[待补 raw]
- 不确定性：Cursor agent mode 在持续进化，结论可能 6 个月后翻转

**判断**：MCP（Model Context Protocol）已成事实标准，选 agent 时优先看 MCP 支持质量。
- 置信度：high
- 有效期：2027-06
- 来源：[modelcontextprotocol/servers 已 star]
- 不确定性：MCP 生态仍在快速演化

**判断**：多 agent harness（ECC、Hermes、superpowers 类）目前更适合观察，不投入生产。
- 置信度：medium
- 有效期：2026-09
- 来源：[ECC、hermes-agent 已 star]
- 不确定性：这类项目 star 数虚高，且大多数没有真实长期用户证言

## 方法或流程

### 选型决策树

```
任务输入
  ├─ 是否需要在终端里跑（CI、远程、长任务）？
  │    └─ 是 → Codex CLI（已用） / Claude Code CLI（待实测）
  │
  ├─ 是否需要 GUI 边看边改、探索陌生代码？
  │    └─ 是 → Cursor / Qoder
  │
  ├─ 是否是跨多文件的复杂重构？
  │    └─ 是 → Claude Code 优先（长上下文）
  │
  ├─ 是否是单文件小修小补？
  │    └─ 是 → 任何工具都行，看哪个开着
  │
  └─ 是否要做 AI 工作流编排？
       └─ 是 → 用 LangGraph / smolagents 自己组，不要用现成 harness
```

### 评估新 agent 的清单

收到新工具推荐时，按这 5 个问题判断要不要试用：

1. **MCP 支持**：是否原生支持 MCP server？支持质量如何？
2. **长任务**：能不能在终端里跑 30 分钟以上而不挂？
3. **上下文窗口**：能不能装下你最大的代码文件 ×5？
4. **可观测**：能不能看到它在调什么工具、烧了多少 token？
5. **退出成本**：试用后想换走，prompt / skill / 配置能不能迁移？

5 个问题里有 3 个不确定，先观察不试用。

### 已淘汰 / 不再投入

- ~~**dify**~~（已观察，未 star）
  - 决策：与已 star 的 multica-ai 生态位重叠，且自己个人开发不需要"企业级 Agent 平台"
  - 时间：2026-06
- ~~**index-tts**~~（不属于 coding agent，记录在 TTS 决策 wiki）
- 待补：实测 Cursor 后若发现局限，写入此处

### 复活检查（重新评估的触发条件）

- 当前主力工具发生重大版本变化（如 Codex CLI 重写）
- 新出现一个被多人推荐 + GitHub star 增速 >5k/月 的工具
- 自己的工作流变化（如开始大量做远程 / CI 任务）
- 季度自评时发现 "实际只用了一个工具"，需要简化

## 限制

- 当前结论基于个人开发场景，不代表团队 / 企业级选型
- 仅针对**编码任务**的 agent；研究 agent（gpt-researcher 等）走另一篇 wiki
- 模型质量比工具壳子更重要，但本 wiki 不评估模型本身
- 价格因素未深入分析；当前所有工具都在免费额度内
- "已淘汰"列表是当下决策，不代表项目本身没价值；半年后可能复活
- 缺少自测对照数据；判断置信度大部分为 medium，需后续 raw 沉淀强化

## 来源

- GitHub stars：
  - https://github.com/openai/codex
  - https://github.com/anthropics/claude-code
  - https://github.com/modelcontextprotocol/servers
  - https://github.com/affaan-m/ECC
  - https://github.com/NousResearch/hermes-agent
  - https://github.com/colbymchenry/codegraph
- raw：[待沉淀]
  - 计划：实测 Codex vs Claude Code 同任务对比，产出 1 篇 raw
  - 计划：MCP server 选型（基于 modelcontextprotocol/servers）产出 1 篇 raw
- profile.md：当前主线包含 AI Agent 工具链
- radar：`reports/stars_profile_2026-06-24.md`
