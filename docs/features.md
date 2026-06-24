# Feature Ledger

本文档维护 karpathy-kb 的当前功能账本，用于回答"系统现在有哪些能力、入口在哪里、如何验证"。架构边界以 `docs/architecture.md` 为准；实现细节以 `scripts/kb.py` 和测试为准。

## 维护规则

- 新增、删除或改变用户可见功能时，先更新本文档，再改实现。
- 只记录已经落地或明确保留的能力，不把阶段计划当成功能状态。
- 每个功能必须能指向入口命令、核心文件和验证方式。
- 状态只使用：`active`、`planned`、`deprecated`。
- 如果功能依赖外部服务，必须写清楚失败边界和降级方式。

## 功能总览

| 功能 | 状态 | 用户入口 | 核心文件 | 验证 |
| --- | --- | --- | --- | --- |
| 读取 source 并创建 raw | active | `python3 scripts/kb.py raw <source>` | `scripts/kb.py`, `templates/raw-note.md` | `python3 scripts/kb.py raw --help` |
| raw 队列查看 | active | `python3 scripts/kb.py list` | `scripts/kb.py` | `python3 scripts/kb.py list` |
| wiki 主题查看 | active | `python3 scripts/kb.py list --wiki` | `scripts/kb.py`, `wiki/` | `python3 scripts/kb.py list --wiki` |
| raw 老化状态查看 | active | `python3 scripts/kb.py list --aging` | `scripts/kb.py` | 单元测试 `TestListAgingColumn` |
| raw 审阅提示词 | active | `python3 scripts/kb.py review <raw-file>` | `scripts/kb.py`, `prompts/raw-review.md` | `python3 scripts/kb.py review --help` |
| 发布提示词 | active | `python3 scripts/kb.py publish-prompt <raw-file>` | `scripts/kb.py`, `prompts/publish.md` | `python3 scripts/kb.py publish-prompt --help` |
| 发布检查清单 | active | `python3 scripts/kb.py publish-checklist <raw-file>` | `scripts/kb.py` | 单元测试 `TestBuildPublishChecklist` |
| 周报 prompt 生成 | active | `python3 scripts/kb.py weekly` | `scripts/kb.py`, `config/roles/`, `templates/weekly_*.md`, `prompts/weekly*.md` | 单元测试 `TestBuildWeeklyPromptTemplate`, `TestWeeklyCache` |
| 角色化输出 | active | `python3 scripts/kb.py weekly --role <role_id>` | `config/roles/*.yaml`, `templates/weekly_*.md` | `python3 scripts/kb.py weekly --role product_builder --no-cache` |
| wiki 编译 prompt | active | `python3 scripts/kb.py compile <topic>` | `scripts/kb.py` | 单元测试 `TestBuildCompilePrompt` |
| compile dry-run | active | `python3 scripts/kb.py compile <topic> --dry-run` | `scripts/kb.py` | 单元测试 `TestCompileDryRun` |
| compile prompt 保存 | active | `python3 scripts/kb.py compile <topic> --output` | `scripts/kb.py`, `reviews/` | 单元测试 `TestCompileOutputPath` |
| 老化扫描 | active | `python3 scripts/kb.py aging` | `scripts/kb.py`, `reviews/` | 单元测试 `TestScanAgingRaws`, `TestScanAgingWikis` |
| 过期条目标记 deprecated | active | `python3 scripts/kb.py deprecate <file>` 或 `python3 scripts/kb.py aging --confirm` | `scripts/kb.py` | 单元测试 `TestDeprecateRaw`, `TestDeprecateWikiJudgment` |
| 健康检查 | active | `python3 scripts/kb.py doctor` | `scripts/kb.py` | `python3 scripts/kb.py doctor` |
| Capture Layer | planned | 未实现 CLI | `docs/architecture.md` | 暂无 |
| 静态知识操作台 kb-site | planned | 设计中 | `docs/superpowers/specs/2026-06-23-kb-site-phase0-phase1-design.md` | 暂无 |

## 核心工作流

### 读取

用途：服务当前问题，不进入知识库。

入口由 Agent 直接调用 MCP `source_reader_read`，不写文件、不更新 wiki。读取 URL、PDF、视频字幕和登录态页面时，优先使用 source-reader MCP。

### 沉淀

用途：把 source 转为 raw 工作台，但不发布到 wiki。

流程：

1. Agent 调用 MCP `source_reader_read` 读取 source。
2. 必要时运行 `python3 scripts/kb.py raw <source>` 创建 raw。
3. Agent 必须补全 raw 的 `Auto Summary`、`Suggestions`、`wiki_targets`。
4. 向用户展示摘要和建议，等待是否发布。

边界：

- `kb.py raw` 依赖本机 source-reader HTTP 服务 `127.0.0.1:8765`。
- `kb.py raw` 只做机械落地，不负责长期价值判断。
- raw 状态只允许 `fetched` 和 `published`。

### 发布

用途：用户确认后，将 raw 编织进长期 wiki。

流程：

1. 运行 `python3 scripts/kb.py publish-checklist <raw-file>`。
2. 运行 `python3 scripts/kb.py publish-prompt <raw-file>` 生成发布上下文。
3. 更新 `wiki/*.md`、`index.md`、`log.md`。
4. 将 raw frontmatter 的 `status` 改为 `published`。
5. 运行 `python3 scripts/kb.py doctor`。

边界：

- 不能在用户未确认时发布。
- wiki 按主题组织，不按来源建笔记。
- 不把 raw 全文搬入 wiki。

### 周报

用途：基于近期 raw、已有 wiki 和角色配置生成周报 prompt。

入口：

```bash
python3 scripts/kb.py weekly
python3 scripts/kb.py weekly --role product_builder --no-cache
python3 scripts/kb.py weekly --output
```

边界：

- 周报是 Output Layer，不重新抓取网页。
- 周报 prompt 可缓存到 `.weekly-cache/`。
- 模板使用 `%%MARKER%%` 字符串替换，不使用 Jinja2。

### 老化管理

用途：发现 raw 和 wiki 判断的有效期风险，并支持显式 deprecated 标注。

入口：

```bash
python3 scripts/kb.py aging
python3 scripts/kb.py aging --output
python3 scripts/kb.py aging --confirm
python3 scripts/kb.py deprecate <file> --reason <reason>
```

边界：

- 已过期内容不删除，只标注 deprecated。
- `aging --confirm` 是交互写入命令，执行前必须确认不会误改目标文件。

## 外部依赖边界

### source-reader

职责：输入读取基础设施。

karpathy-kb 只通过 MCP 或本机 HTTP 服务使用它，不维护 reader 实现。

失败表现：

- `source-reader service unreachable`
- 登录态不足导致读取质量低
- 大内容只读到 preview

处理方式：

- 当前任务读取优先用 MCP `source_reader_read`。
- 需要落 raw 时才用 `kb.py raw`。
- 服务没启动时，在 source-reader 独立仓库启动服务。

### Obsidian Vault

职责：默认 raw 落地位置。

解析顺序：

1. `config.json` 中的 `raw_dir`
2. `~/Documents/Obsidian Vault/00_Inbox`
3. 其他 Obsidian 候选目录

失败表现：

- `raw_dir 未配置`

处理方式：

- 创建 `config.json` 显式指定 `raw_dir`。

## 验证基线

编码改动完成后至少运行：

```bash
python3 -m unittest discover tests -v
python3 scripts/kb.py doctor
```

文档-only 改动至少运行：

```bash
python3 scripts/kb.py doctor
```

涉及 CLI 参数时补充：

```bash
python3 scripts/kb.py --help
python3 scripts/kb.py <command> --help
```

## 已知缺口

- Capture Layer 仅在架构中定义，尚无 CLI 和持久目录。
- `kb-site` 仍处于设计阶段，尚未成为当前可用功能。
- `kb.py raw` 创建的 raw 仍需要 Agent 立即补齐摘要和建议，脚本本身不会自动生成 LLM 内容。
- `doctor` 检查 raw/wiki/index/log/role 配置闭环，但不验证 Markdown 内容质量。
