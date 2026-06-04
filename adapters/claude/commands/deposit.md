---
description: Read a source and create a raw note for later confirmation.
argument-hint: <source>
---

沉淀 `$ARGUMENTS`。

请从知识库根目录直接调用自动模式：

```bash
python3 scripts/kb.py raw "$ARGUMENTS" --mode auto --browser-profile .source-reader/profiles/default --interactive-login --login-timeout-ms 180000 --read-depth standard
```

这个命令会先走低成本 fast reader；遇到登录墙或 JS 空壳时，自动切到 Playwright 持久化 profile。需要登录时会打开浏览器等待用户登录，不要再询问用户是否重试。

如果错误提示 Playwright 未安装，直接运行一次：

```bash
python3 scripts/install.py --target claude --install-playwright
```

如果仍然失败，先运行：

```bash
python3 scripts/source_reader.py --doctor --format md
```

根据 doctor 的明确建议继续处理；只有缺少用户登录、账号授权或多个 vault 无法判断时才询问用户。

创建 raw 后，读取该 raw，并在 raw 中补充自动摘要、结合 `profile.md` 的建议、可能的 wiki 目标和待确认问题。不要更新 wiki。最后询问用户是否发布。
