# Runbook

这份手册描述一次真实使用时该怎么执行。它不是产品设计文档，而是日常操作约定。

## 读取

用户输入：

```text
读取 <source>
```

执行规则：

- 只读取 source，回答当前问题。
- 不创建 raw。
- 不更新 wiki。
- 如果 source 明显值得长期保留，只建议用户改用 `沉淀`，不主动沉淀。

## 沉淀

用户输入：

```text
沉淀 <source>
```

执行步骤：

1. 用 source-reader 获取内容。
2. 运行 `python3 scripts/kb.py raw <source>` 创建 raw。
3. 运行 `python3 scripts/kb.py review <raw-file>` 生成审阅提示词。
4. LLM 根据提示词补全 raw 的 `Auto Summary`、`Suggestions`、`Questions`。
5. LLM 向用户展示核心摘要、建议和发布问题。

停止点：

- 如果用户没有确认发布，只保留 raw。
- 不把 reviewed 或 approved 写入任何文件。

## 发布

用户输入：

```text
发布
```

执行前提：

- 用户已经在对话里明确确认。
- 必须能定位最近一次或用户指定的 raw。

执行步骤：

1. 运行 `python3 scripts/kb.py publish-prompt <raw-file>` 生成发布提示词。
2. LLM 判断新建还是更新已有 wiki。
3. 更新 `wiki/*.md`、`index.md`、`log.md`。
4. 把 raw frontmatter 的 `status` 从 `fetched` 改为 `published`。
5. 回复用户更新了哪些文件，以及后续问题。

## URL 读取边界

V1 source-reader 已经覆盖一组低成本读取策略：

- GitHub repo：默认只读 README。
- GitHub blob：只读 raw 文件。
- GitHub issue / PR：只读正文和前 12 条评论。
- GitHub release note：只读 release notes。
- 视频：优先读取字幕，不下载视频。
- 普通网页：抽取 HTML 文本并按 `--max-chars` 截断。
- JS 渲染网页：`--mode auto --browser-profile <dir>` 检测到 JS 空壳后使用 Playwright 渲染读取。
- 登录态网页：`--mode browser/auto --browser-profile <dir>` 使用持久化 profile 复用登录态。
- 需要首次登录的网页：增加 `--interactive-login`，在浏览器中登录后继续读取。
- 本地 Markdown / TXT / HTML：按文本读取。

仍需要后续增强的输入：

- 登录态网页：完善不同站点的正文选择器和登录状态诊断。
- JS 渲染网页：完善正文选择器和接口型页面的降噪。
- PDF / 论文：抽取文本、标题、作者、页码引用。
- 播客：优先已有 transcript，其次转写。
- 讨论串：区分主帖、高赞评论、争议点和结论。
