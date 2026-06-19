---
description: Publish a confirmed raw note into wiki/index/log.
argument-hint: [raw-file]
---

发布 `$ARGUMENTS`。

只有用户已经明确确认可以发布时才执行。请从知识库根目录调用：

```bash
python3 scripts/kb.py publish-prompt $ARGUMENTS
```

根据生成的发布提示词执行以下步骤：

1. 读取 `index.md`，找出与本次内容相关的所有已有 wiki 页面，逐一判断是否需要补充或修正（往回织）。
2. 写入或更新当前主题 wiki。优先更新已有主题，不要按来源创建重复 wiki。
3. 更新 `index.md`：新建页面追加一行 `[[wiki/文件名]] — 一句话摘要`，已有页面摘要有重大变化时同步更新。
4. 更新 `log.md`，把对应 raw 的 `status` 改为 `published`。
