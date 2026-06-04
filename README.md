# Karpathy KB

这是一个面向个人使用的 Obsidian 知识库项目，底层思路来自 Karpathy 的 LLM-maintained wiki：保留 raw 事实源，让 LLM 维护一组可读、可演进的 wiki 笔记。

## 核心原则

- 链接本身不是触发器，用户意图才是触发器。
- `读取 <source>` 只服务当前任务，不写入知识库。
- `沉淀 <source>` 才进入知识库流程：读取 source，写入 raw，在 raw 中生成摘要、建议和待确认问题。
- wiki 只有在用户明确确认后才生成或更新。
- 持久状态只保留 `fetched` 和 `published`，中间的 reviewed/approved 只存在于对话里。

## Source Reader 边界

读 URL / PDF / 视频字幕 / 登录态页面这些"输入层"职责，已经独立成 `~/Documents/source-reader/`，并通过 MCP（server 名 `source-reader`）注册到 Claude / Codex。

本仓库不再包含 reader 实现：

- Claude / Codex 直接调用 MCP 工具 `source_reader_read` / `source_reader_action` / `source_reader_feedback`。
- `scripts/kb.py raw <source>` 通过 `127.0.0.1:8765` 调本机 source-reader 服务，把读取结果落成 raw。
- 服务未启动时到独立仓库执行：`cd ~/Documents/source-reader && python3 scripts/source_reader.py serve --host 127.0.0.1 --port 8765`。

karpathy-kb 只负责"读到的资料是否值得长期保存"这一层判断。

## 目录

```text
karpathy-kb/
  AGENTS.md                 # LLM 维护知识库的工作规则
  CLAUDE.md                 # Claude Code 工作规则
  commands.md               # 读取/沉淀/发布等触发词
  README.md                 # 项目说明
  index.md                  # Obsidian 首页
  log.md                    # 发布日志
  profile.md                # 个人偏好和长期目标
  prompts/                  # LLM 工作提示词
  raw/                      # 原始资料、读取结果、摘要和建议
  scripts/                  # kb.py：raw 落地、list、review/publish 提示词
  wiki/                     # 经确认后沉淀的长期知识
  templates/                # raw/wiki 模板
  adapters/                 # Claude / Codex 适配文件镜像
```

## 最小工作流

1. 用户说：`沉淀 <url 或文件>`
2. LLM 通过 MCP `source_reader_read` 读取内容（或直接调 `scripts/kb.py raw`）。
3. LLM 创建 `raw/YYYY-MM-DD-短标题.md`，保存原文、元数据、摘要、建议和确认问题。
4. LLM 向用户展示摘要、建议和可能的 wiki 更新方案。
5. 用户说：`发布` 或明确确认。
6. LLM 更新 `wiki/`、`index.md`、`log.md`，并把 raw 状态改为 `published`。

## 本地辅助脚本

只剩一个：`scripts/kb.py`。

```bash
python3 scripts/kb.py raw <source>                                # 走本机 source-reader 服务读 source，写 raw
python3 scripts/kb.py raw <source> --mode auto --interactive-login --read-depth standard
python3 scripts/kb.py raw <source> --max-chars 24000              # 控制写入 raw 的原文长度
python3 scripts/kb.py list --status fetched                       # 查看 raw 队列
python3 scripts/kb.py review <raw-file>                           # 生成 review 提示词
python3 scripts/kb.py publish-prompt <raw-file>                   # 生成 publish 提示词
```

`kb.py` 只做机械动作：调服务、按模板落 raw、拼提示词。总结、建议、发布判断仍由 LLM 完成。

## Source Reader 安装与维护

参见 `~/Documents/source-reader/README.md` 和 `~/Documents/source-reader/CLAUDE.md`。在那里完成：

- Node / Playwright 安装、profile 管理
- MCP 注册到 Claude / Codex
- 服务启动、status、doctor 等运维命令

karpathy-kb 不再托管这些命令，避免和独立仓库分叉。
