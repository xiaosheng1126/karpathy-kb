# Implementation Guide

本文档定义 karpathy-kb 的功能实现流程。目标是让后续新增能力时，先明确规则、再小步实现、最后验证闭环。

## 基本原则

- 规则先行：涉及 schema、目录、状态、工作流的变化，先改 `docs/architecture.md` 或本文档。
- 功能同步：用户可见功能变化，必须同步 `docs/features.md`。
- 最小改动：只改当前功能需要的文件，不顺手重构相邻代码。
- 标准库优先：`scripts/kb.py` 当前只依赖 Python stdlib，新依赖必须先评估。
- 测试优先：新增纯函数先写单元测试；CLI wiring 至少通过现有测试和 help/doctor 验证。
- 状态保守：raw 持久状态只保留 `fetched` 和 `published`，不要引入临时状态。

## 开发前检查

开始实现前先确认：

```bash
git status --short
python3 scripts/kb.py --help
python3 scripts/kb.py doctor
```

如果工作区已有无关改动，不要回滚；只在自己的变更范围内工作。

## 变更分级

### 文档-only

适用：补说明、更新功能账本、修正流程描述。

必须更新：

- 相关文档本身
- 如果影响当前功能状态，同步 `docs/features.md`

验证：

```bash
python3 scripts/kb.py doctor
```

### CLI 行为变更

适用：新增子命令、增加参数、改变输出格式、写入新文件。

必须更新：

- `scripts/kb.py`
- `tests/test_kb.py`
- `docs/features.md`
- 必要时更新 `README.md`、`commands.md` 或 `runbook.md`

验证：

```bash
python3 -m unittest discover tests -v
python3 scripts/kb.py --help
python3 scripts/kb.py <command> --help
python3 scripts/kb.py doctor
```

### Schema 或生命周期变更

适用：raw/wiki/capture frontmatter、状态、字段语义变化。

必须更新：

- `docs/architecture.md`
- `templates/*.md`
- `scripts/kb.py`
- `tests/test_kb.py`
- `docs/features.md`

要求：

- Raw Schema v1 只能新增可选字段，不能删除或重命名字段。
- 破坏性变更必须升级 `schema_version`，并提供迁移脚本或迁移步骤。
- wiki 判断条目必须保留置信度、有效期、来源和不确定性。

### 新输出类型或新角色

适用：新增日报、产品周报、文章 prompt，或新增 role profile。

优先路径：

1. 新增 `config/roles/<role_id>.yaml`。
2. 新增或复用 `templates/<template>.md`。
3. 新增或复用 `prompts/<instructions>.md`。
4. 用 `python3 scripts/kb.py weekly --role <role_id> --no-cache` 验证。

不应修改核心代码，除非现有 Role Profile 协议无法表达需求。

### 新长期功能

适用：Capture Layer、kb-site、索引生成、自动编译等新模块。

必须先写设计：

- 如果改变系统层级或数据契约，更新 `docs/architecture.md`。
- 如果只是阶段实现，新增 `docs/superpowers/plans/YYYY-MM-DD-topic.md`。
- 如果会成为长期用户能力，预先在 `docs/features.md` 标记为 `planned`。

## 新增 CLI 子命令流程

1. 定义成功标准

示例：

```text
新增 generate-index 命令，读取 wiki 和 role 配置，输出 generated/*.json。
成功标准：三个 JSON 文件存在，包含 generated_at，测试覆盖解析函数，doctor 不报错。
```

2. 拆出纯函数

优先把可测试逻辑写成纯函数，例如：

```python
def build_xxx_report(...) -> str:
    ...
```

避免把所有逻辑塞进 `main()` 的 argparse 分支。

3. 写测试

测试放在 `tests/test_kb.py`，按功能新建 `TestXxx` 类。优先覆盖：

- 正常输入
- 空输入
- 边界字段缺失
- 重复写入或重复添加
- 不应处理的文件，如 `README.md`

4. 接入 argparse

在 `main()` 中新增：

```python
xxx_cmd = sub.add_parser("xxx", help="...")
xxx_cmd.add_argument(...)
```

分支结构保持现有风格：

```python
if args.command == "xxx":
    ...
    return 0
```

5. 更新文档

至少更新：

- `docs/features.md`
- 如命令属于日常触发词，更新 `commands.md`
- 如命令改变日常操作，更新 `runbook.md`
- 如命令体现新层级能力，更新 `docs/architecture.md`

6. 验证

```bash
python3 -m unittest discover tests -v
python3 scripts/kb.py xxx --help
python3 scripts/kb.py doctor
```

## 新增 Role Profile 流程

1. 创建配置文件：

```yaml
role_id: example_role
display_name: 示例角色
focus_areas:
  - 示例领域
source_scope:
  wiki_topics: ["*"]
  raw_status: [fetched, published]
  time_window_days: 7
output_template: templates/weekly_example.md
instructions_file: prompts/weekly_example.md
cold_start_threshold: 3
```

2. 创建模板文件。

模板使用 `%%MARKER%%` 占位符。当前可用占位符以 `docs/architecture.md` 的 Output Template 约定为准。

3. 创建角色指令文件。

指令文件只写该角色如何判断，不重复模板结构。

4. 验证：

```bash
python3 scripts/kb.py weekly --role example_role --no-cache
python3 scripts/kb.py doctor
```

5. 更新 `docs/features.md` 中的角色化输出说明。

## 新增 Template 占位符流程

1. 在 `docs/architecture.md` 的 Output Template 约定中新增占位符说明。
2. 在 `_build_weekly_prompt_from_root()` 的 `ctx` 中加入对应 key。
3. 给 `_render_template()` 或 weekly prompt 增加测试。
4. 更新相关模板文件。

验证：

```bash
python3 -m unittest discover tests -v
python3 scripts/kb.py weekly --no-cache
```

## 新增 Doctor 检查流程

适用：新增配置文件、目录或闭环关系后，需要防止系统静默失效。

实现位置：

- 检查逻辑：`run_doctor()`
- 输出格式：`build_doctor_report()`
- 测试：`TestDoctor`

要求：

- 会导致流程不可用的问题标记 `ERROR`。
- 信息缺失但不阻断流程的问题标记 `WARN`。
- `doctor` 不自动修复文件，只报告问题。

验证：

```bash
python3 -m unittest discover tests -v
python3 scripts/kb.py doctor
```

## 新增 Raw 字段流程

1. 先更新 `docs/architecture.md` 的 Raw Schema。
2. 更新 `templates/raw-note.md`。
3. 更新 `create_raw()` 输出。
4. 如字段参与查询，新增 parser 或 accessor 测试。
5. 如字段影响 doctor，新增 doctor 检查。

注意：

- 字段新增必须向后兼容。
- 旧 raw 缺字段时，代码必须能降级处理。
- 不要用 ad hoc 字符串判断替代已有 helper，优先复用 `frontmatter_value()` 和 `frontmatter_list_value()`。

## 新增 Wiki 结构流程

1. 先更新 `docs/architecture.md` 的 Wiki Schema 或判断格式。
2. 更新 `templates/wiki-note.md`。
3. 更新相关解析函数和测试。
4. 更新 publish prompt 或 checklist，确保 Agent 会按新结构发布。

注意：

- wiki 是长期知识层，不保存来源全文。
- 已过时判断不删除，使用删除线和原因标注。
- 新 wiki 必须登记到 `index.md`，发布记录写入 `log.md`。

## 新增外部服务依赖流程

原则上避免新增外部依赖。确实需要时，先回答：

- 为什么 stdlib 或现有 source-reader 不能解决？
- 依赖的许可证、维护状态、体积和安全风险是什么？
- 离线或服务失败时如何降级？
- 是否需要修改 CI/CD、系统配置或全局依赖？

命中全局依赖、系统配置、CI/CD、密钥等红线时，必须先让用户确认。

## 文件写入约定

- 手工编辑使用 `apply_patch`。
- 不主动删除文件。
- 不主动 commit 或 push。
- 生成类输出优先写入既有目录：`reviews/`、raw_dir、`wiki/`。
- 新目录必须先有规则文件或在上级规则中定义职责。

## 验收清单

完成任何实现类任务前检查：

- [ ] 是否先更新了规则或确认无需规则变化？
- [ ] 是否同步了 `docs/features.md`？
- [ ] 是否只修改了请求相关文件？
- [ ] 是否为新逻辑补了测试？
- [ ] 是否跑过 `python3 -m unittest discover tests -v`？
- [ ] 是否跑过 `python3 scripts/kb.py doctor`？
- [ ] 是否没有触碰 commit、push、部署、密钥、CI/CD 等红线？
- [ ] 是否说明了未覆盖的风险或后续观察点？
