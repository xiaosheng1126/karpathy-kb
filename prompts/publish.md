# Publish Prompt

用户已经确认可以发布。请基于指定 raw 更新知识库。

## 发布规则

- 优先更新已有 wiki。
- 只有主题确实独立时才新建 wiki。
- 不把 raw 全文搬进 wiki。
- 保留来源链接或 raw 引用。
- 把不确定性写清楚。

## 必须更新

- `wiki/*.md`
- `index.md`
- `log.md`
- 对应 raw 的 `status: published`

## 发布后回复

告诉用户：

- 更新了哪些文件
- 新增或修改了哪些主题
- 还有哪些后续问题

