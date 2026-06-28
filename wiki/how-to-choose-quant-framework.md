---
schema_version: "1"
status: draft
tags: [quant, trading, backtest, finance, decision]
sources: []
created_at: 2026-06-24
updated_at: 2026-06-24
last_verified_at: 2026-06-24
valid_until: 2026-12
---

# 如何选择量化 / 金融 Agent 框架

## 结论

**当前默认组合（2026-06，个人研究 / 非商用）**：

- **数据层 + AI agent 入口**：OpenBB（刚 star，AGPLv3，支持 MCP）
- **建模 / 因子研究 / A 股**：qlib（已 star，MIT，微软出品）
- **回测 / 实盘执行**：Lean（已 star，Apache，多市场，C#/Py）
- **组合分析 / tearsheet**：quantstats（刚 star，Apache，pip 即用）
- **多 agent 决策研究**：TradingAgents（已 star，论文型，仅观察）
- ❌ **不选**：rqalpha（仅限非商用，且 qlib + Lean 已覆盖）

不要追求"一个框架吃所有环节"。**数据 → 建模 → 回测 → 组合分析 → 实盘**是五个独立环节，当前没有任何开源项目能在五项都领先。按环节组合更稳。

## 适用场景

- 个人量化研究、策略原型验证
- A 股 / 港股 / 美股 / 加密货币的策略回测
- 想用 AI agent 辅助选股、新闻聚合、决策支持
- 学习量化框架架构

不适用：

- 实盘资金管理（这些框架都不带券商风控，需自建）
- 高频交易（毫秒级延迟需 C++ 自研）
- 商业化产品（rqalpha 协议受限，OpenBB 高级功能闭源）

## 判断依据

**判断**：量化研究链路当前不存在"通吃赢家"，按环节组合是唯一可行策略。
- 置信度：high
- 有效期：2026-12
- 来源：[待补 raw，基于已 star 项目的 README 比对]
- 不确定性：未做端到端实战；理论比对可能与实际工作流有差距

**判断**：OpenBB 是当前最有 AI 友好度的金融数据平台（原生 MCP 支持）。
- 置信度：medium
- 有效期：2026-12
- 来源：OpenBB README "Financial data platform for analysts, quants and AI agents"
- 不确定性：商业版功能未开源，免费层数据范围/限速需自测

**判断**：qlib 在 A 股 ML 建模上是开源生态最成熟的选择。
- 置信度：high
- 有效期：2027-06
- 来源：微软维护，长期高活跃，社区共识
- 不确定性：实盘表现强依赖数据源质量和因子设计，框架本身不能保证盈利

**判断**：Lean 是跨市场回测的工业级开源选项，但学习曲线陡。
- 置信度：high
- 有效期：2027-06
- 来源：QuantConnect 商业产品的开源核心，长期演进
- 不确定性：Lean 偏 C# 文化，纯 Python 用户上手需克服一些痛点

**判断**：quantstats 是组合分析"开箱即用"的事实标准，pip 安装即可。
- 置信度：high
- 有效期：2027-06
- 来源：2026-01 仍在更新，社区共识
- 不确定性：分析维度固定，复杂归因需自行扩展

**判断**：TradingAgents 类多 agent 决策框架目前仍属"研究品"，不投入实盘。
- 置信度：medium
- 有效期：2026-09
- 来源：TauricResearch/TradingAgents、HKUDS/Vibe-Trading 已 star
- 不确定性：论文级项目通常缺少长期生产用户证言，star 数虚高

**判断**：rqalpha 在 A 股回测上有积累，但协议限制 + 已被 qlib 覆盖，没有 star 价值。
- 置信度：medium
- 有效期：2026-12
- 来源：项目 README 明确"仅限非商业使用"
- 不确定性：若专做 A 股策略发行且不商用，rqalpha 例程仍有参考价值

**判断**：开源量化框架本身**不能保证盈利**，工具选型只是降低试错成本。
- 置信度：high
- 有效期：永久
- 来源：行业常识
- 不确定性：无；这是必须前置说明的限制

## 方法或流程

### 选型决策树

```
量化任务输入
  ├─ 我要做什么？
  │
  ├─ 拿数据 / 看新闻 / AI 辅助分析
  │    └─ OpenBB（CLI / Python / MCP）
  │
  ├─ 因子研究 / ML 建模 / A 股
  │    └─ qlib（带数据集，可直接跑教程）
  │
  ├─ 多市场回测 / 实盘对接
  │    └─ Lean（学习曲线高，但能跨市场）
  │
  ├─ 已有策略，想做组合分析报告
  │    └─ quantstats（pip install，10 分钟出 tearsheet）
  │
  ├─ 想看看 AI agent 怎么决策
  │    └─ TradingAgents 跑示例，仅学习不实盘
  │
  └─ 纯学习国内量化生态？
       └─ 看 daily_stock_analysis、QuantDinger 等中文项目（已 star）
```

### 完整研究链路（建议按环节组合）

```
[数据] OpenBB / qlib 自带数据
    ↓
[建模] qlib（A 股 ML） / 自写 Python（其他市场）
    ↓
[回测] Lean（跨市场） / qlib 内置（A 股）
    ↓
[分析] quantstats tearsheet
    ↓
[决策] 人工 / TradingAgents 辅助（仅研究）
    ↓
[执行] 不在本 wiki 范围（需另选券商 API + 风控）
```

### 评估新量化框架的清单

收到推荐时按这 5 个问题筛选：

1. **市场覆盖**：支持哪些市场？A 股数据是否合规？
2. **数据来源**：是否绑定特定数据商？是否需要订阅？
3. **协议**：MIT / Apache 还是 GPL / 仅限非商用？
4. **回测真实度**：是否考虑滑点 / 手续费 / 涨跌停 / T+1？
5. **维护活跃度**：最近 6 个月提交次数？issue 响应速度？

第 4 项不过关的框架直接跳过——用错了比不用更危险。

### 已淘汰 / 不再投入

- ~~**rqalpha**~~（已观察，未 star）
  - 决策：协议限制（仅限非商用） + qlib 已覆盖 A 股
  - 时间：2026-06
  - 复活条件：专做 A 股 + 明确不商用 + 需要参考完整策略例程

### 复活检查（重新评估的触发条件）

- 出现新的 Apache/MIT 协议、AI 原生设计的量化框架
- 当前主力项目重大架构变化（如 qlib 引入新 RL 范式）
- 个人研究方向变化（如开始做加密货币高频）
- 季度自评时发现"实际只跑了 1-2 次回测"，需简化决策

## 限制

- 当前结论基于个人研究 / 学习场景，不代表机构级投研选型
- 仅评估**开源框架**；商业平台（QuantConnect Cloud / 聚宽 / 米筐 / 优矿）未对比
- 缺少端到端实战数据；多数判断置信度 medium，需自测补强
- 量化框架不能替代投资决策；本 wiki 不构成任何投资建议
- A 股数据合规性需个人确认；部分项目可能涉及数据源使用条款
- 模型质量比框架壳子更重要；本 wiki 不评估具体策略 / 模型

## 来源

- GitHub stars：
  - https://github.com/OpenBB-finance/OpenBB
  - https://github.com/microsoft/qlib
  - https://github.com/QuantConnect/Lean
  - https://github.com/ranaroussi/quantstats
  - https://github.com/TauricResearch/TradingAgents
  - https://github.com/HKUDS/Vibe-Trading
  - https://github.com/Fincept-Corporation/FinceptTerminal
  - https://github.com/ZhuLinsen/daily_stock_analysis
  - https://github.com/brokermr810/QuantDinger
  - https://github.com/ricequant/rqalpha （未 star，已淘汰）
- raw：[待沉淀]
  - 计划：实测 OpenBB MCP 接入流程，产出 1 篇 raw
  - 计划：qlib 跑通 A 股 demo + quantstats 出 tearsheet 的端到端流程
- profile.md：当前主线包含量化交易 / 金融 Agent
- radar：`reports/stars_profile_2026-06-24.md`
