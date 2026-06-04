# Karpathy KB

这是一个面向个人使用的 Obsidian 知识库项目，底层思路来自 Karpathy 的 LLM-maintained wiki：保留 raw 事实源，让 LLM 维护一组可读、可演进的 wiki 笔记。

## 核心原则

- 链接本身不是触发器，用户意图才是触发器。
- `读取 <source>` 只服务当前任务，不写入知识库。
- `沉淀 <source>` 才进入知识库流程：读取 source，写入 raw，在 raw 中生成摘要、建议和待确认问题。
- wiki 只有在用户明确确认后才生成或更新。
- 持久状态只保留 `fetched` 和 `published`，中间的 reviewed/approved 只存在于对话里。

## 目录

```text
karpathy-kb/
  AGENTS.md                 # LLM 维护知识库的工作规则
  commands.md               # 读取/沉淀/发布等触发词
  README.md                 # 项目说明
  index.md                  # Obsidian 首页
  log.md                    # 发布日志
  profile.md                # 个人偏好和长期目标
  prompts/                  # LLM 工作提示词
  raw/                      # 原始资料、读取结果、摘要和建议
  scripts/                  # 本地辅助脚本
  wiki/                     # 经确认后沉淀的长期知识
  source-reader/            # 独立的输入读取能力设计
  templates/                # raw/wiki 模板
```

## 最小工作流

1. 用户说：`沉淀 <url 或文件>`
2. LLM 调用 source-reader 读取内容。
3. LLM 创建 `raw/YYYY-MM-DD-短标题.md`，保存原文、元数据、摘要、建议和确认问题。
4. LLM 向用户展示摘要、建议和可能的 wiki 更新方案。
5. 用户说：`发布` 或明确确认。
6. LLM 更新 `wiki/`、`index.md`、`log.md`，并把 raw 状态改为 `published`。

## 本地辅助脚本

先提供两个很小的零依赖脚本：

```bash
python3 scripts/source_reader.py <source> --format md
python3 scripts/source_reader.py <source> --format md --read-depth preview
python3 scripts/source_reader.py <source> --format json --max-chars 16000
```

`source_reader.py` 只负责读取输入，并尽量节省 token：

- GitHub repo：默认只读取 README，不遍历整个项目。
- GitHub blob：读取 raw 文件，不读取页面外壳。
- GitHub issue/PR：读取正文和前 12 条评论，不拉完整时间线。
- GitHub release：读取 release notes，不抓整个 releases 页面。
- 视频：如果本机有 `yt-dlp`，优先读取字幕，不下载视频。
- 普通网页：抽取 HTML 文本，并按 `--max-chars` 做头尾保留。
- 本地文件：按文本读取，HTML 会抽正文。
- 大文档：先用 `--read-depth preview` 输出快速预览和下一步动作，再由用户决定是否深读、总结或沉淀。

`kb.py` 用于把 source-reader 的结果生成 raw 草稿：

```bash
python3 scripts/kb.py raw <source>
python3 scripts/kb.py raw <source> --read-depth standard
```

这个脚本只负责机械读取和落 raw，不负责总结、建议和发布判断。可以用 `--max-chars` 控制写入 raw 的原文长度。

常用命令：

```bash
python3 scripts/kb.py list --status fetched
python3 scripts/kb.py review <raw-file>
python3 scripts/kb.py publish-prompt <raw-file>
```

- `list`：查看当前 raw 队列。
- `review`：把 profile、review 规则和 raw 拼成一段提示词，供 LLM 生成摘要、建议和待确认问题。
- `publish-prompt`：用户确认发布后，生成发布提示词，指导 LLM 更新 wiki、index、log 和 raw 状态。

## 安装到 Codex / Claude

这个知识库可以作为可移植套件安装到任意 Obsidian vault。安装器会复制核心协议、模板、脚本和 `source-reader`，再按目标 Agent 写入适配文件。

自动安装到 Obsidian vault：

```bash
python3 scripts/install.py --target both
```

如果有多个 Obsidian vault，可以按名称或路径指定：

```bash
python3 scripts/install.py --target both --vault-name "Obsidian Vault"
```

```bash
python3 scripts/install.py --target both --vault /path/to/obsidian-vault
```

如果希望安装时顺手准备登录态/JS 页面读取能力：

```bash
python3 scripts/install.py --target both --vault /path/to/obsidian-vault --install-playwright
```

自动检测 vault 时也可以直接安装 browser 依赖：

```bash
python3 scripts/install.py --target both --install-playwright
```

只安装某一侧：

```bash
python3 scripts/install.py --target codex --vault /path/to/obsidian-vault
python3 scripts/install.py --target claude --vault /path/to/obsidian-vault
```

默认不会覆盖已有文件；需要覆盖模板时显式加 `--force`。

Codex 适配会生成：

```text
.codex-plugin/plugin.json
skills/karpathy-kb/SKILL.md
AGENTS.md
```

Claude 适配会生成：

```text
CLAUDE.md
.claude/commands/read.md
.claude/commands/deposit.md
.claude/commands/publish.md
.claude/commands/update-kb.md
```

两侧都复用同一套 `scripts/source_reader.py` 和 `scripts/kb.py`，因此读取网页、GitHub、PDF、视频字幕、JS 渲染页面和登录态页面的能力不会分叉。

对登录态页面，Agent 应直接使用：

```bash
python3 scripts/source_reader.py <source> --mode auto --browser-profile .source-reader/profiles/default --interactive-login --login-timeout-ms 180000 --read-depth preview --format md
```

它会先低成本读取；遇到登录墙或 JS 空壳时自动打开持久化浏览器 profile。用户只需要在浏览器里完成登录，后续同域名页面会复用登录态。
