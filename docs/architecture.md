# Karpathy KB 架构设计

> 本文档是系统的唯一架构权威来源。所有实现、Agent 行为、模板设计必须以本文档为准。
> 修改规范时：先改本文档，再改实践，不要反过来。

---

## 设计原则

1. **Schema 优先**：层间数据格式在任何实现之前锁定。接口稳定，实现才能独立演化。
2. **接口先于实现**：即使某层 v1 不实现，也必须定义它的输入输出契约，防止上下游各自为政。
3. **高内聚低耦合**：每层只做一件事，层间通过稳定接口通信，不允许跨层直接访问数据。
4. **LLM 输出边界明确**：区分"必须固化的判断"和"可重新生成的建议"，保证 wiki 稳定。
5. **知识有生命周期**：知识从沉淀到过期，系统必须能感知和标记，不允许永久有效的隐性假设。
6. **扩展不改系统**：新角色、新输出类型、新 source 类型的加入，应只需新增配置或模板文件，不改核心代码和 schema。

---

## 系统全景

```
External Sources
  ↓  [URL / GitHub / PDF / Video / 本地文件]
source-reader（独立 MCP 服务）
  ↓  [ReaderResult]
Ingestion Adapter（kb.py raw）
  ↓  [RawNote v1]
Raw Layer（raw/*.md）
  ↓  [RawQuery]
Knowledge Compiler（v2 实现，v1 仅定义接口）
  ↓  [CompileResult]
Wiki Layer（wiki/*.md）
  ↓  [WikiQuery + RoleProfile]
Output Layer（kb.py weekly / kb.py article）
  ↓  [WeeklyReport / Article / ...]
```

**单向流原则**：数据从上往下流动。唯一的例外是"往回织"——新 raw 进入时，Knowledge Compiler 回溯更新相关 wiki，但这通过显式触发实现，不是隐式的双向依赖。

---

## 各层职责边界

### source-reader（独立服务）

**做**：识别输入类型、选择读取策略、处理登录态、输出 ReaderResult。

**不做**：判断资料价值、创建 raw、更新 wiki、维护用户知识结构。

接入方式：MCP 工具 `source_reader_read` / `source_reader_action` / `source_reader_feedback`，或本机服务 `127.0.0.1:8765`。

---

### Ingestion Adapter

**做**：调用 source-reader，把 ReaderResult 转换并写入 RawNote，立即填充 LLM fixed 字段（摘要、关键点、wiki_targets）。

**不做**：判断是否值得沉淀（由用户决定）、修改 wiki、生成周报。

当前实现：`scripts/kb.py raw <source>`

---

### Raw Layer

**做**：保存事实源和工作台数据，包括元数据、原始摘录、固化摘要、可刷新建议、知识生命周期字段。

**不做**：长期知识判断、直接用于对外发布。

状态只有两个：`fetched`（已保存）→ `published`（用户确认后已发布至 wiki）。

---

### Knowledge Compiler（v1 仅定义接口，v2 实现）

**做**：把多个相关 raw 编译成 wiki 主题页，发现新资料对旧判断的影响，触发"往回织"。

**不做**：直接与用户交互、决定发布。

接口见下方"Knowledge Compiler 接口"章节。

---

### Wiki Layer

**做**：保存用户确认后值得复用的长期知识，按主题组织，每条判断带置信度和有效期。

**不做**：保存来源全文、自动接受 Compiler 输出（必须用户确认）。

---

### Output Layer

**做**：读取 raw/wiki，结合 Role Profile，按 Output Template 生成周期性输出。

**不做**：重新抓取网页、创建 raw、修改 raw 状态、自动发布 wiki。

当前实现：`scripts/kb.py weekly`（技术者周报）

---

## Raw Schema v1（锁定）

> v1 字段一旦确定不得删除或重命名，只允许新增可选字段（向后兼容）。
> 需要破坏性变更时，升级 `schema_version` 并写迁移脚本。

### Frontmatter

```yaml
schema_version: "1"
status: fetched                  # fetched | published

# --- Source 元数据 ---
source_type: ""                  # github_repo | blog | pdf | video | discussion | local_file
title: ""
url: ""
local_path: ""
author: ""
published_at: ""                 # 来源发布时间 ISO8601，可为空
saved_at: ""                     # 用户保存时间 ISO8601（用于周报窗口计算）
fetched_at: ""                   # 实际读取时间 ISO8601

# --- 读取质量 ---
reader: ""                       # source-reader 使用的 reader 类型
read_quality: ""                 # high | medium | low

# --- LLM Fixed（沉淀时生成，不重新生成）---
summary: ""
key_points: []
wiki_targets: []                 # 建议更新的 wiki 主题名称

# --- 知识生命周期 ---
confidence: medium               # high | medium | low
valid_until: ""                  # 预期有效期 ISO8601 date，可为空
deprecated_reason: ""            # 已过时时填写原因

# --- Compiler Hints ---
related_raws: []                 # 关联 raw 的文件名（无路径）
```

### 正文结构

```markdown
## Original Content

原文摘录或转写文本（保持可追溯）。

## Auto Summary（LLM Fixed — 不重新生成）

### 核心观点

### 关键细节

### 事实 / 观点 / 推测

### 限制和不确定性

## Suggestions（LLM Refreshable — 可重新生成）

### 对你的建议

### 是否值得沉淀

### 建议创建或更新的 wiki
```

**`saved_at` vs `published_at` 区别**：`published_at` 是来源的发布日期；`saved_at` 是用户把这条资料加入知识库的时间。周报基于 `saved_at` 过滤"本周保存的内容"，而不是"本周发布的内容"。

---

## Wiki Schema v1（锁定）

### Frontmatter

```yaml
schema_version: "1"
status: published
tags: []
sources: []                      # 来源 raw 文件名列表
created_at: ""
updated_at: ""
```

### 判断条目格式

wiki 页面内每条具体判断应遵循以下格式，保证知识生命周期可追溯：

```markdown
**判断**：X 工具值得持续跟踪。
- 置信度：medium
- 有效期：2026-12
- 来源：raw/xxx.md
- 不确定性：尚未实际试用
```

过期或被推翻的判断不删除，改为：

```markdown
**判断**：~~X 工具值得持续跟踪。~~（已过时：2026-09，竞品 Y 已取代）
```

---

## LLM 输出边界

系统中所有 LLM 生成的内容分为两类，必须严格区分：

### Fixed（固化，不重新生成）

| 字段 / 内容 | 位置 | 原因 |
|------------|------|------|
| `summary` | raw frontmatter | 代表用户当时的理解，重新生成会丢失历史视角 |
| `key_points` | raw frontmatter | 同上 |
| `wiki_targets` | raw frontmatter | 影响 Compiler 路由，变动会破坏关联 |
| `## Auto Summary` 全文 | raw 正文 | 同上 |

**原则**：凡是"用户当时怎么看这件事"的记录，必须固化。

### Refreshable（可重新生成）

| 字段 / 内容 | 位置 | 原因 |
|------------|------|------|
| `## Suggestions` 全文 | raw 正文 | 行动建议随时间和上下文变化是合理的 |
| 周报正文 | reviews/*.md | 每次生成都基于最新 raw/wiki，应该是当前视角 |

**原则**：凡是"现在应该怎么做"的建议，可以重新生成。

---

## 知识生命周期

每条知识（raw 和 wiki 判断）有显式生命周期，系统必须感知并在输出中呈现。

```
[saved] → [active] → [aging] → [deprecated]
```

| 状态 | 触发条件 | 系统行为 |
|------|---------|---------|
| active | 默认 | 正常进入周报和 Compiler |
| aging | `valid_until` 距今 ≤ 30 天 | 周报中标注"⚠ 即将过期，建议验证" |
| deprecated | 用户确认，或 `valid_until` 已过期 | 不进入周报，但不删除 |

**`deprecated` 不等于删除**：过期判断保留在文件中，加删除线标注。这是系统的历史记录，也是未来"往回看"的依据。

---

## Knowledge Compiler 接口（v1 定义，v2 实现）

> v1 不实现此接口，但必须在此定义清楚。所有在 v1 中涉及"多 raw 聚合"的操作，都应以此接口为蓝图手动执行，为 v2 自动化留出路径。

### 输入

```python
compile(
    raw_ids: list[str],          # 参与编译的 raw 文件名
    topic: str,                  # 目标 wiki 主题
    existing_wiki: str | None    # 已有 wiki 文件路径，可为空
) -> CompileResult
```

### 输出 CompileResult

```python
@dataclass
class CompileResult:
    topic: str
    summary: str
    judgments: list[Judgment]
    sources: list[str]           # raw 文件名
    uncertainty: str
    suggested_actions: list[str]
    weave_back_targets: list[str]  # 应回溯更新的其他 wiki 主题
```

```python
@dataclass
class Judgment:
    statement: str
    confidence: str              # high | medium | low
    valid_until: str | None      # ISO8601 date
    basis: str
    sources: list[str]           # 支撑此判断的 raw 文件名
```

### 往回织（Weave-Back）

新 raw 进入时，Compiler 检查 `wiki_targets` 和 `related_raws`，判断是否需要更新已有 wiki 主题。更新流程：

1. Compiler 生成 `weave_back_targets` 列表。
2. 向用户呈现"以下 wiki 主题受此 raw 影响，建议更新：..."。
3. 用户确认后才执行更新。

---

## 角色扩展协议

新角色的加入只需新增一个 Role Profile 数据文件，不改代码。

### Role Profile Schema

文件位置：`config/roles/<role_id>.yaml`

```yaml
role_id: technical_practitioner
display_name: 技术从业者
focus_areas:
  - Android
  - HarmonyOS
  - Flutter
  - AI Coding
  - Engineering Tools
source_scope:
  wiki_topics: ["*"]             # "*" 表示全部，或指定主题列表
  raw_status: [fetched, published]
  time_window_days: 7            # 周报读取最近 N 天的 raw
output_template: templates/weekly_technical.md
cold_start_threshold: 5          # raw 数量低于此值时触发冷启动提示
```

### Output Template 约定

模板文件使用 Markdown + `%%MARKER%%` 风格占位符（非 Jinja2，纯字符串替换）。模板只负责结构，不包含判断逻辑。判断逻辑由 Output Layer 的 LLM 调用完成。

**可用占位符：**

| 占位符 | 替换内容 |
|--------|---------|
| `%%WEEK_LABEL%%` | 如 `2026-W25` |
| `%%COLD_START_WARNING%%` | 冷启动警告块（可为空） |
| `%%AGING_SECTION%%` | 老化预警块（可为空） |
| `%%PROFILE%%` | `profile.md` 全文 |
| `%%FOCUS_AREAS%%` | 关注领域逗号分隔字符串 |
| `%%WEEKLY_INSTRUCTIONS%%` | `prompts/weekly.md` 全文 |
| `%%RAWS_HEADER%%` | 如 `2026-06-16 至 2026-06-23，共 3 条` |
| `%%RAWS_SECTION%%` | 各 raw 文件内容拼接块 |
| `%%WIKI_SECTION%%` | 各 wiki 文件内容拼接块 |
| `%%CUTOFF_DATE%%` | 如 `2026-06-16` |
| `%%TODAY%%` | 如 `2026-06-23` |
| `%%RAW_COUNT%%` | 数字字符串，如 `3` |

### 示例：product_builder 角色（待新建）

当需要添加"产品思考者"角色时，只需新增两个文件，零代码变更：

**`config/roles/product_builder.yaml`**：

```yaml
role_id: product_builder
display_name: 产品思考者
focus_areas:
  - 产品设计
  - 用户需求
  - 竞品分析
  - AI 产品
  - 商业模式
source_scope:
  wiki_topics: ["*"]
  raw_status: [fetched, published]
  time_window_days: 7
output_template: templates/weekly_product.md
cold_start_threshold: 3
```

**`templates/weekly_product.md`**：以 `templates/weekly_technical.md` 为基础，替换标题和结构指令即可，所有 `%%MARKER%%` 占位符通用。

验证方式（创建文件后）：`python3 scripts/kb.py weekly --role product_builder`

---

## 冷启动策略

系统在 raw 积累足够之前，输出质量有限。v1 内置以下冷启动意识：

1. 周报生成时，检查 `time_window_days` 内的 raw 数量。
2. 数量低于 `cold_start_threshold`（默认 5）时，在周报开头插入提示：
   ```
   > ⚠ 本周输入偏少（N 条），以下判断仅供参考，建议补充更多资料后重新生成。
   ```
3. 提供"补录"路径：`kb.py raw <url> --saved-at 2026-06-01` 允许补录历史 raw，`saved_at` 由用户指定。

---

## 扩展规则

以下是新功能进入系统时的约束，目标是在不修改核心系统设计的前提下扩展能力：

| 扩展类型 | 需要做什么 | 不需要改什么 |
|---------|-----------|------------|
| 新输出类型（日报、文章） | 新增 Output Template 文件，在 Role Profile 里指定 | 核心代码、Raw Schema、Wiki Schema |
| 新角色 | 新增 Role Profile 数据文件 | 核心代码 |
| 新 source 类型 | 在 source-reader 层处理，`source_type` 是字符串不是枚举 | Raw Schema |
| 新 wiki 主题 | Knowledge Compiler 自然支持，无需预注册 | 任何配置 |
| 更换 LLM 模型 | 更新调用配置 | Schema、接口、模板 |
| Raw Schema 升级 | 升级 `schema_version`，写迁移脚本处理历史文件 | 现有历史 raw（向后兼容） |

---

## 分阶段路线图

### v1（当前）目标：建立可运转的最小系统

- [x] 按本文档更新 Raw Schema 模板（新增 `schema_version`、`saved_at`、`confidence`、`valid_until`）
- [x] 按本文档更新 Wiki Schema 模板（新增 `schema_version`、`created_at`，判断条目加生命周期字段）
- [x] 创建 `config/roles/technical_practitioner.yaml`（Role Profile 数据文件）
- [x] 实现 `kb.py weekly`：读取 raw/wiki，结合 Role Profile 生成技术者周报
- [x] 周报冷启动检测（raw < threshold 时插入提示）
- [x] 补录 raw 支持 `--saved-at` 参数

**v1 约束**：Knowledge Compiler 不实现，但本文档中的接口定义就是 v2 的合同。

### v2 目标：知识产生复利

- [x] Knowledge Compiler 基础实现：`kb.py compile` + `find_raws_for_topic()` + `build_compile_prompt()`
- [x] 往回织：`find_matching_wikis()` 集成进 `build_publish_prompt()`，发布时自动提示匹配 wiki 和缺失主题
- [x] raw → wiki 关联索引：`find_raws_for_topic()` 在编译时动态扫描 `wiki_targets`，当前规模无需持久索引

### v3 目标：多角色支持

- [x] Role Profile 加载器：`load_role_profile()` 从 `config/roles/<role_id>.yaml` 动态读取
- [ ] 新增第二个角色（`product_builder` 或 `writer`）——参见"角色扩展协议"章节示例，仅需新增 2 个文件
- [x] Output Template 渲染引擎：`_render_template()` + `%%MARKER%%` 占位符体系，`templates/weekly_technical.md` 已生效

### v4 目标：知识生命周期管理

- [x] 自动 aging 检测：`kb.py aging` 扫描 raw `valid_until` 和 wiki 判断有效期，支持 `--threshold`、`--output`
- [x] 周报中展示"即将过期的判断"模块：`build_aging_block()` 已集成进 `_build_weekly_prompt_from_root()`
- [ ] aging → deprecated 交互确认流：`kb.py aging --confirm`（见 v5）

### v5 目标：闭环与扩展

- [ ] `kb.py aging --confirm`：过期条目一键交互确认并写入 deprecated 标注
- [ ] 新增 `product_builder` 角色 Profile + 周报模板
- [ ] `kb.py list --aging`：list 命令集成 aging 状态列

---

## 成功标准

v1 完成后，后续 Agent 应该能清楚回答：

- `source-reader` 是输入基础设施，不属于知识库核心，不在本仓库维护。
- Raw Schema v1 已锁定，新字段只能新增，不能删除或重命名。
- `saved_at` 是用户保存时间，`published_at` 是来源发布时间，周报用前者。
- `Auto Summary` 内容一旦写入不重新生成；`Suggestions` 内容可以重新生成。
- Knowledge Compiler 接口已定义，v2 实现时按接口对接，不改 Raw Schema 和 Wiki Schema。
- 新角色只需新增 `config/roles/<role_id>.yaml`，不改代码。
- 知识过期用 deprecated 标注，不删除。
