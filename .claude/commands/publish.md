---
description: Publish a confirmed raw note into wiki/index/log.
argument-hint: [raw-file]
---

发布 `$ARGUMENTS`。

只有用户已经明确确认可以发布时才执行。请从知识库根目录调用：

```bash
python3 scripts/kb.py publish-prompt $ARGUMENTS
```

根据生成的发布提示词更新 `wiki/`、`index.md`、`log.md`，并把对应 raw 的 `status` 改为 `published`。优先更新已有主题 wiki，不要按来源创建重复 wiki。
