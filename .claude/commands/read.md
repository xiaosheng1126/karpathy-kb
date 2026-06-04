---
description: Read a source for the current task without creating raw or wiki notes.
argument-hint: <source>
---

读取 `$ARGUMENTS`。

优先调用 MCP 工具 `source_reader_read`，参数建议：

- `source`：上面这个 URL 或路径。
- `mode`：`auto`（默认 fast，遇到 JS 空壳或登录墙自动升级）。
- `read_depth`：`preview`（内容多时先要预览）。
- `interactive_login`：true（遇到登录墙时由 source-reader 服务自己打开浏览器等待登录）。

不要使用 Claude 内置 `Fetch` / `WebFetch`。MCP server 名是 `source-reader`，由独立项目 `~/Documents/source-reader/` 提供。

读完后只回答当前问题，不创建 raw、不更新 wiki。如果结果里包含 `Next Operations` / `actions`：

- 需要登录时执行 `login_with_browser`。
- 用户要求继续时执行 `continue_deep_read`。
- 用户只想看结构时执行 `extract_outline`。
- 用户只想看代码 / API / 命令时执行 `extract_code`。
- 用户反馈结果可用或不对时执行 `mark_result_good` / `mark_result_bad`。

如果 MCP 工具不可用（连接失败 / 没注册），到独立仓库排查：`cd ~/Documents/source-reader && python3 scripts/source_reader.py status`。karpathy-kb 这一侧不再保留 doctor / install 命令。
