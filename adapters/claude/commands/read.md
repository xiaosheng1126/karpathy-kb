---
description: Read a source for the current task without creating raw or wiki notes.
argument-hint: <source>
---

读取 `$ARGUMENTS`。

请从知识库根目录直接调用自动模式：

```bash
python3 scripts/source_reader.py "$ARGUMENTS" --mode auto --browser-profile .source-reader/profiles/default --interactive-login --login-timeout-ms 180000 --read-depth preview --format md
```

这个命令会先走低成本 fast reader；遇到登录墙、JS 空壳或读取质量很差时，自动切到 Playwright 持久化 profile。需要登录时会打开浏览器等待用户登录，不要再询问用户是否重试。

如果错误提示 Playwright 未安装，直接运行一次：

```bash
python3 scripts/install.py --target claude --install-playwright
```

如果仍然失败，先运行：

```bash
python3 scripts/source_reader.py --doctor --format md
```

根据 doctor 的明确建议继续处理；只有缺少用户登录、账号授权或多个 vault 无法判断时才询问用户。

只回答当前问题，不创建 raw，不更新 wiki。内容很多时先给快速预览和下一步操作。
