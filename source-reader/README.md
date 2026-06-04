# Source Reader

source-reader 是独立能力，负责把各种输入读取并规范化为 raw source。它服务知识库，也可以服务普通开发任务。

## 为什么独立

读取 URL 和读取知识不是同一件事。

- source-reader 解决：如何把复杂输入读进来。
- knowledge-base 解决：这些信息对用户有什么长期价值。

这样 `读取 <source>` 可以只用于当前任务，`沉淀 <source>` 才进入知识库流程。

## V1 支持范围

- 普通 URL：静态网页、博客、官方文档。
- JS 渲染网页：用 Playwright 持久化 profile 渲染后读取正文。
- 登录态网页：用 Playwright 持久化 profile 保存登录态后读取。
- GitHub：repo、gist、issue、PR、release note、raw 文件。
- PDF/论文：arXiv PDF 优先读取摘要页；普通 PDF 先标记为待增强。
- 视频字幕：YouTube、B站。
- 讨论串：HN、Reddit、V2EX、X thread。
- 本地输入：Markdown、TXT、HTML、截图、聊天记录、粘贴文本。

## Token 节省策略

- 能读 raw 就不读网页外壳。
- 能读 README 就不遍历仓库。
- 能读字幕就不处理音视频本体。
- 能读摘要页就不直接读取整篇 PDF。
- 能读主帖和少量高价值评论，就不拉完整讨论串。
- 默认先走 `fast`，只有登录墙或 JS 空壳才用 `browser/auto`。
- 默认 `max_chars=24000`，超出时保留头部和尾部，中间明确标记截断。
- 支持 `--read-depth preview|standard|full`，先用 `preview` 快速判断是否值得继续。

## 读取模式

```bash
python3 scripts/source_reader.py <url> --mode fast --format md
python3 scripts/source_reader.py <url> --mode browser --browser-profile .source-reader/profiles/default --format md
python3 scripts/source_reader.py <url> --mode auto --browser-profile .source-reader/profiles/default --format md
python3 scripts/source_reader.py <url> --mode browser --browser-profile .source-reader/profiles/default --interactive-login --format md
python3 scripts/source_reader.py <url> --mode auto --browser-profile .source-reader/profiles/default --interactive-login --login-timeout-ms 180000 --read-depth preview --format md
python3 scripts/source_reader.py <url> --mode auto --read-depth preview --format md
python3 scripts/source_reader.py --doctor --format md
```

- `fast`：默认模式，HTTP 读取，成本最低。
- `browser`：强制使用 Playwright 持久化 profile，适合语雀、飞书、Notion、JS 渲染站点。
- `auto`：先 `fast`，如果检测到登录墙或 JS 空壳，再切到 `browser`。配合 `--interactive-login` 时，不需要先询问用户是否重试；工具会直接打开持久化浏览器等待登录。

## 阅读深度

- `preview`：默认预算 6000 字符，输出标题、结构、前导片段和下一步动作，适合先判断资料价值。
- `standard`：默认预算 24000 字符，适合普通总结和 raw 沉淀。
- `full`：默认预算 80000 字符，适合用户确认后的深读；仍然保留截断标记，避免失控读取。

如果显式传入 `--max-chars`，以 `--max-chars` 为准。

## 下一步操作协议

`source_reader.py` 会在 JSON 输出里提供 `preview` 和 `next_actions`，在 Markdown 输出里显示 `Quick Preview` 和 `Next Operations`。

当前动作包括：

- `深读全文`：用 `--read-depth full` 重新读取。
- `结构化总结`：提示 LLM 基于当前内容输出背景、核心观点、风险和建议。
- `沉淀为 raw`：调用 `scripts/kb.py raw` 进入 Obsidian raw 流程。
- `追问细节`：保留给用户针对章节、实现、风险继续提问。
- `登录后重试`：当读取被登录墙或错误阻断时出现，使用 Playwright 持久化 profile 重新读取。

这套“操作”先以稳定数据协议存在，后续可以映射到聊天 UI、Obsidian 命令、Raycast 或快捷指令。

第一次使用 browser profile 时，需要让 Playwright 打开可见 Chrome，手动登录目标站点。后续同一 profile 会复用登录态。不要直接使用日常 Chrome 主 Profile，避免锁冲突和隐私边界不清。

如果页面跳到登录页，使用 `--interactive-login`。工具会等待你在打开的浏览器里扫码或账号登录，然后继续抽取正文。

如果 browser 模式失败，先运行 `python3 scripts/source_reader.py --doctor --format md`。doctor 会检查 Node、npm、Playwright、browser reader 脚本和持久化 profile，并给出下一步命令。

Playwright 是可选依赖；需要 browser 模式时在项目目录安装：

```bash
python3 scripts/install.py --target both --install-playwright
```

## 统一输出

```yaml
source_id:
input_type:
source_type:
status:
title:
url:
local_path:
author:
published_at:
fetched_at:
reader:
read_quality:
metadata:
assets:
errors:
```

正文输出应包含：

- 原始内容或可追溯摘录
- 读取质量说明
- 结构化摘要
- 对用户的建议
- 是否建议发布到 wiki
- 建议创建或更新的 wiki 条目
- 需要用户确认的问题
