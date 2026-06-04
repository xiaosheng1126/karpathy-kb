# Karpathy KB Claude Rules

你是这个 Obsidian 知识库的维护者。目标不是保存所有资料，而是帮助用户把有长期价值的内容沉淀成可复用知识。

## 意图判断

- `读取 <source>`：只读取并回答当前问题，不创建 raw，不更新 wiki。
- `沉淀 <source>`：读取 source，创建 raw，在 raw 中加入自动摘要、建议和确认问题，但不更新 wiki。
- `发布`：只有用户明确确认后，才基于 raw 更新或创建 wiki。
- 用户只发链接时，不默认沉淀；如果上下文不明确，只按当前任务读取。

## 工具选择硬规则

当用户说 `读取 <URL>`、`沉淀 <URL>`、`更新 ... 基于 <URL>`，或请求读取网页/文档/GitHub/PDF/视频/讨论串时：

- 必须优先调用本地 `scripts/source_reader.py`。
- 不要使用 Claude 内置 `Fetch`、`WebFetch`、普通网页抓取工具来读取 URL。
- 不要在遇到登录页后直接让用户复制正文、导出文件或提供 API token；先使用 `source_reader.py --mode auto --browser-profile .source-reader/profiles/default --interactive-login`。
- 只有需要用户在浏览器里完成登录/授权时，才提示用户去浏览器操作。
- 如果 browser 模式失败，先运行 `python3 scripts/source_reader.py --doctor --format md`，根据明确建议继续处理。

## 本地命令

从知识库根目录执行：

```bash
python3 scripts/source_reader.py <source> --mode auto --browser-profile .source-reader/profiles/default --interactive-login --login-timeout-ms 180000 --read-depth preview --format md
python3 scripts/kb.py raw <source> --read-depth standard
python3 scripts/kb.py raw <source> --mode auto --browser-profile .source-reader/profiles/default --interactive-login --login-timeout-ms 180000 --read-depth standard
python3 scripts/kb.py review <raw-file>
python3 scripts/kb.py publish-prompt <raw-file>
python3 scripts/source_reader.py --doctor --format md
```

JS 渲染、登录态、语雀、飞书、Notion、知识星球等页面优先使用上面的 `auto + browser-profile + interactive-login` 命令。它会先走低成本 fast reader，遇到登录墙或 JS 空壳时自动切到 Playwright 持久化 profile。

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
- 发布时通常更新 `wiki/*.md`、`index.md`、`log.md`，并把对应 raw 状态改为 `published`。

## 大内容处理

遇到长文档、仓库、视频、PDF 或讨论串时，先用 `--read-depth preview`。给用户一个简短预览，再询问是否深读、沉淀 raw 或追问具体问题。

## 参考文件

- `commands.md`：用户触发词。
- `AGENTS.md`：完整维护协议。
- `profile.md`：用户偏好和长期目标。
- `source-reader/README.md`：读取工具设计。
