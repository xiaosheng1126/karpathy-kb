# Runbook

这份手册描述一次真实使用时该怎么执行。它不是产品设计文档，而是日常操作约定。

## 读取

用户输入：

```text
读取 <source>
```

执行规则：

- 通过 MCP `source_reader_read` 读取 source，回答当前问题。
- 不创建 raw。
- 不更新 wiki。
- 如果 source 明显值得长期保留，只建议用户改用 `沉淀`，不主动沉淀。

## 沉淀

用户输入：

```text
沉淀 <source>
```

执行步骤：

1. 通过 MCP `source_reader_read` 获取内容（必要时同步调 `source_reader_action`）。
2. 运行 `python3 scripts/kb.py raw <source>` 创建 raw（走本机 source-reader 服务）。
3. 运行 `python3 scripts/kb.py review <raw-file>` 生成审阅提示词。
4. LLM 根据提示词补全 raw 的 `Auto Summary`、`Suggestions`、`Questions`。
5. LLM 向用户展示核心摘要、建议和发布问题。

停止点：

- 如果用户没有确认发布，只保留 raw。
- 不把 reviewed 或 approved 写入任何文件。

## 发布

用户输入：

```text
发布
```

执行前提：

- 用户已经在对话里明确确认。
- 必须能定位最近一次或用户指定的 raw。

执行步骤：

1. 运行 `python3 scripts/kb.py publish-prompt <raw-file>` 生成发布提示词。
2. LLM 判断新建还是更新已有 wiki。
3. 更新 `wiki/*.md`、`index.md`、`log.md`。
4. 把 raw frontmatter 的 `status` 从 `fetched` 改为 `published`。
5. 回复用户更新了哪些文件，以及后续问题。

## URL 读取边界

URL / GitHub / 视频字幕 / JS 渲染 / 登录态 / 本地文档 / PDF 的读取策略全部由 source-reader 服务负责，本仓库不再维护这部分文档。需要确认能力或调整参数时去 `~/Documents/source-reader/README.md`。

karpathy-kb 这一侧的硬约束：

- 不能用 Claude 内置 Fetch / WebFetch 读 URL。
- `kb.py raw` 依赖本机 source-reader 服务（默认 `127.0.0.1:8765`）；服务没起时直接报错，由用户去独立仓库 `python3 scripts/source_reader.py serve` 启动。
- 大内容默认 `read_depth=preview`，确认后再 `standard` / `full`。
