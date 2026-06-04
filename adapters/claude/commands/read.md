---
description: Read a source for the current task without creating raw or wiki notes.
argument-hint: <source>
---

读取 `$ARGUMENTS`。

如果 MCP tool 已配置，优先调用 `source_reader_read`。未配置 MCP 时，从知识库根目录调用本地服务：

```bash
python3 scripts/source_reader.py remote-read "$ARGUMENTS" --read-depth preview --format md
```

这个命令只连接本机 `127.0.0.1` source-reader 服务；外部联网、Playwright、缓存和登录态由服务负责。不要使用 Claude 内置 Fetch，也不要因为普通网络读取失败让用户选择重试路径。

如果本地服务未启动，先启动服务，不要让用户介入：

```bash
python3 scripts/source_reader.py serve --host 127.0.0.1 --port 8765
```

如果必须直接读取，才使用 fallback：

```bash
python3 scripts/source_reader.py "$ARGUMENTS" --mode auto --browser-profile .source-reader/profiles/default --interactive-login --login-timeout-ms 180000 --read-depth preview --format md
```

fallback 会先走低成本 fast reader；遇到登录墙、JS 空壳或读取质量很差时，自动切到 Playwright 持久化 profile。需要登录时会打开浏览器等待用户登录，不要再询问用户是否重试。

如果错误提示 Playwright 未安装，直接运行一次：

```bash
python3 scripts/install.py --target claude --install-runtime --install-mcp --start-service
```

如果仍然失败，先运行：

```bash
python3 scripts/source_reader.py --doctor --format md
```

根据 doctor 的明确建议继续处理；只有缺少用户登录、账号授权或多个 vault 无法判断时才询问用户。

读取结果里如果出现 `Next Operations` / `actions`，优先按这些操作继续：

- 需要登录时执行 `login_with_browser`。
- 用户要求继续时执行 `continue_deep_read`。
- 用户只想看结构时执行 `extract_outline`。
- 用户只想看代码/API/命令时执行 `extract_code`。
- 用户反馈结果可用或不对时，执行 `mark_result_good` / `mark_result_bad`。
- 不要绕过本地 action 重新使用 Claude 内置 Fetch。

只回答当前问题，不创建 raw，不更新 wiki。内容很多时先给快速预览和下一步操作。
