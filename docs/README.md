# Docs

`docs/` 保存产品、架构和流程规范，不保存来源正文，不替代 raw/wiki/review。

## 文件规则

- 架构设计放在 `docs/architecture.md`。
- 当前功能清单和状态放在 `docs/features.md`，用于回答"系统现在有哪些能力"。
- 新功能实现步骤、验收标准和测试约定放在 `docs/implementation-guide.md`，用于指导后续改动落地。
- 阶段计划可放在 `docs/plans/`，文件名使用 `YYYY-MM-DD-topic.md`。
- 文档只描述规则、边界和决策，不记录每次资料读取的内容。
- 规则变更先改文档，再改脚本或工作流。

## 职责边界

- `architecture.md` 是 schema、层级边界和路线图的权威来源。
- `features.md` 是已实现能力和入口命令的维护账本，不写设计推演。
- `implementation-guide.md` 是开发操作指南，不替代具体阶段计划。
- `superpowers/plans/` 只保存阶段性执行计划，计划完成后应把长期有效的信息回填到上述稳定文档。
