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

创建 raw 后，**立即编辑 raw 文件**，填充以下内容（不留占位符）：
- `## Auto Summary`：核心观点、关键细节、事实/观点/推测区分、限制和不确定性。
- `## Suggestions`：结合 `profile.md` 给出对用户的具体建议、是否值得沉淀、建议更新哪篇 wiki。
- frontmatter `wiki_targets`：填入建议的目标 wiki 页面名称。

不要更新 wiki。向用户展示摘要和建议，询问是否发布。
