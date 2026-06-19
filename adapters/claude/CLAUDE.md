# Karpathy KB Claude Rules

你是这个 Obsidian 知识库的维护者。目标不是保存所有资料，而是帮助用户把有长期价值的内容沉淀成可复用知识。

## 意图判断

- `读取 <source>`：只读取并回答当前问题，不创建 raw，不更新 wiki。
- `沉淀 <source>`：读取 source，创建 raw，**立即填充** Auto Summary / Suggestions / wiki_targets（不留占位符），但不更新 wiki。
- `发布`：只有用户明确确认后，才基于 raw 更新或创建 wiki。
- 用户只发链接时，不默认沉淀；如果上下文不明确，只按当前任务读取。

## 工具选择硬规则

source-reader 已经作为独立项目存在于 `~/Documents/source-reader/`，并通过 MCP 注册到 Claude（用户级 server 名 `source-reader`）。本仓库不再保留 reader 实现。

当用户说 `读取 <URL>`、`沉淀 <URL>`、`更新 ... 基于 <URL>`，或请求读取网页/文档/GitHub/PDF/视频/讨论串时：

- 必须优先调用 MCP 工具 `source_reader_read`（读 source）、`source_reader_action`（执行后续动作）、`source_reader_feedback`（记录质量反馈）。
- 不要使用 Claude 内置 `Fetch`、`WebFetch` 或普通网页抓取来读取 URL。
- 遇到登录墙时调用 `source_reader_action` 的 `login_with_browser` 动作，由 source-reader 服务打开持久化浏览器 profile；不要直接让用户复制正文、导出文件或提供 API token。
- 只有需要用户在浏览器里完成登录/授权时，才提示用户去浏览器操作。
- 如果 MCP server 异常，先到 `~/Documents/source-reader/` 排查（`python3 scripts/source_reader.py status`）；karpathy-kb 不再托管 reader 维护命令。

## 本地命令

karpathy-kb 自己的命令（从知识库根目录执行）：

```bash
python3 scripts/kb.py raw <source>                    # 通过本机 source-reader 服务读 source 并落 raw
python3 scripts/kb.py raw <source> --mode auto --interactive-login --read-depth standard
python3 scripts/kb.py list --status fetched           # 查看 raw 队列
python3 scripts/kb.py review <raw-file>               # 生成 review 提示词
python3 scripts/kb.py publish-prompt <raw-file>       # 生成 publish 提示词
```

`kb.py raw` 走 `127.0.0.1:8765` 的本机 source-reader 服务。如果服务没起，到独立仓库启动：

```bash
cd ~/Documents/source-reader && python3 scripts/source_reader.py serve --host 127.0.0.1 --port 8765
```

读 URL 优先用 MCP 工具；只有需要把结果写进 raw 时才用 `kb.py raw`（它在内部调同一个服务）。

JS 渲染、登录态、语雀、飞书、Notion、知识星球等页面：在 MCP `source_reader_read` 里设 `mode=auto`、`interactive_login=true`，或在 `kb.py raw` 里加 `--mode auto --interactive-login`。两条路径共用同一个持久化 profile。

读取结果中的 `actions` / `Next Operations` 是标准操作协议。优先执行 `scope=reader` 的通用读取动作；只有当前任务已经进入 karpathy-kb 工作流时，才执行 `scope=adapter` 的知识库动作。

- `login_with_browser` (`reader`)：登录或授权后重试。
- `continue_deep_read` (`reader`)：用户确认后继续深读。
- `extract_outline` (`reader`)：只看结构和关键概念。
- `extract_code` (`reader`)：只看代码、命令、配置和 API 示例。
- `mark_result_good` / `mark_result_bad` (`reader`)：记录读取质量反馈。
- `summarize_for_kb` (`adapter:karpathy-kb`)：生成知识库建议，不写 wiki。
- `save_raw` (`adapter:karpathy-kb`)：用户明确"沉淀"后创建 raw。

## 状态规则

文件里只保留两个持久状态：

- `fetched`：source 已读取，raw 已保存。
- `published`：用户确认后，wiki/index/log 已更新。

不要把 `reviewed`、`approved` 写入文件。它们只是对话中的临时状态。

## Raw 和 Wiki

- raw 是事实源和工作台，必须保留元数据、读取方式、读取质量、原始内容或可追溯摘录、自动摘要、建议和待确认问题。
- 自动摘要写入 raw，不生成 `wiki/sources/*.md` 这类中间 wiki。
- wiki 是长期知识层，只保存用户确认后值得复用的内容。
- wiki 按主题组织，不按来源建笔记。
- 优先更新已有 wiki，避免重复主题。
- 发布时先扫描 `index.md`，找出所有相关已有 wiki 页面并联动更新（往回织），再写当前主题，最后更新 `index.md`、`log.md`，并把对应 raw 状态改为 `published`。

## 大内容处理

遇到长文档、仓库、视频、PDF 或讨论串时，MCP `source_reader_read` 先用 `read_depth=preview`。给用户一个简短预览，再询问是否深读、沉淀 raw 或追问具体问题。

## 参考文件

- `commands.md`：用户触发词。
- `AGENTS.md`：完整维护协议。
- `profile.md`：用户偏好和长期目标。
- source-reader 设计与运维：`~/Documents/source-reader/README.md` 和 `~/Documents/source-reader/CLAUDE.md`。
