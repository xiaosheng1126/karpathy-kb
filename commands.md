# Commands

这份文件定义日常使用时的触发词。链接、文件或文本本身不代表要沉淀，只有命令表达的意图才触发对应流程。

## 读取

```text
读取 <source>
```

用途：服务当前问题，不写入 raw，不更新 wiki。

适合场景：

- 开发时临时读取官方文档。
- 查一个 API 用法。
- 分析某个 issue 或报错。
- 让 LLM 帮你理解一篇文章，但暂时不沉淀。

LLM 行为：

- 调用 source-reader 获取内容。
- 直接回答当前问题。
- 不创建文件。
- 如果发现内容明显值得沉淀，可以建议用户改用 `沉淀`。

## 沉淀

```text
沉淀 <source>
```

用途：进入知识库流程，生成 raw，但不更新 wiki。

LLM 行为：

- 调用 source-reader 读取内容。
- 创建 `raw/YYYY-MM-DD-短标题.md`。
- 在 raw 中写入原文或可追溯摘录、自动摘要、建议、待确认问题。
- 向用户展示摘要和建议，询问是否发布到 wiki。

本地辅助：

```bash
python3 scripts/source_reader.py <source> --format md --max-chars 24000
python3 scripts/source_reader.py <source> --format md --read-depth preview
python3 scripts/source_reader.py <source> --mode auto --browser-profile .source-reader/profiles/default --format md --max-chars 24000
python3 scripts/source_reader.py <source> --mode browser --browser-profile .source-reader/profiles/default --interactive-login --format md --max-chars 24000
python3 scripts/kb.py raw <source> --max-chars 24000
python3 scripts/kb.py raw <source> --read-depth standard
python3 scripts/kb.py raw <source> --mode auto --browser-profile .source-reader/profiles/default --max-chars 24000
python3 scripts/kb.py raw <source> --mode browser --browser-profile .source-reader/profiles/default --interactive-login --max-chars 24000
python3 scripts/kb.py review <raw-file>
```

`source_reader.py` 可单独用于 `读取` 场景；`kb.py raw` 会调用同一套读取策略创建 raw。

`source_reader.py` 的输出包含 `Quick Preview` 和 `Next Operations`，这些动作是当前 CLI 版本的下一步操作：

- 深读全文
- 结构化总结
- 沉淀为 raw
- 追问细节
- 登录后重试

## 发布

```text
发布
```

用途：用户确认后，把最近一次 raw 沉淀进 wiki。

LLM 行为：

- 读取相关 raw。
- 判断应新建还是更新 wiki。
- 更新 `wiki/`、`index.md`、`log.md`。
- 把 raw 状态改为 `published`。

本地辅助：

```bash
python3 scripts/kb.py publish-prompt <raw-file>
```

## 更新

```text
更新 <wiki主题> 基于 <source>
```

用途：明确要求用新 source 更新已有主题。

这个命令等价于：

1. `沉淀 <source>`
2. 用户确认后发布到指定 wiki 主题

## 对比

```text
对比 <source A> 和 <source B>
```

用途：当前任务分析为主，默认不沉淀。只有用户说“沉淀这次对比”时才创建 raw。
