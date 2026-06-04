---
description: Read a source and create a raw note for later confirmation.
argument-hint: <source>
---

沉淀 `$ARGUMENTS`。

从知识库根目录执行：

```bash
python3 scripts/kb.py raw "$ARGUMENTS" --mode auto --interactive-login --read-depth standard
```

`kb.py raw` 通过 `127.0.0.1:8765` 调本机 source-reader 服务（独立项目 `~/Documents/source-reader/`），先走低成本 fast reader，遇到登录墙 / JS 空壳时自动切到 Playwright 持久化 profile。需要登录时由服务打开浏览器等待用户操作，不要再询问。

如果报错 `source-reader service unreachable`：

```bash
cd ~/Documents/source-reader && python3 scripts/source_reader.py serve --host 127.0.0.1 --port 8765
```

karpathy-kb 不再托管 reader 安装 / doctor 命令；reader 端的运维到独立仓库处理。

创建 raw 后，读取该 raw，并在 raw 中补充自动摘要、结合 `profile.md` 的建议、可能的 wiki 目标和待确认问题。不要更新 wiki。最后询问用户是否发布。
