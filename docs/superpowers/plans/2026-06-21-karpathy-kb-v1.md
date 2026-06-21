# Karpathy KB v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 v1 架构，锁定 Raw/Wiki Schema，建立 Role Profile 配置体系，实现 `kb.py weekly` 生成技术者周报 prompt，并支持 `--saved-at` 补录历史 raw。

**Architecture:** `kb.py` 是纯机械脚本，不调用 LLM，只负责收集数据并生成 prompt 供 LLM 消费。`weekly` 命令读取时间窗口内的 raw 文件（基于 `saved_at`）和 wiki 文件，拼装成一份结构化 prompt，打印到 stdout。Role Profile 是 YAML 配置文件，用简单行解析读取，不引入外部依赖。

**Tech Stack:** Python 3.9+（仅 stdlib）、Markdown + YAML frontmatter、无外部依赖

---

## 文件清单

| 操作 | 路径 | 说明 |
|------|------|------|
| 修改 | `templates/raw-note.md` | 新增 schema_version、saved_at、confidence、valid_until 等字段 |
| 修改 | `templates/wiki-note.md` | 新增 schema_version、created_at，补充判断条目格式说明 |
| 创建 | `config/roles/technical_practitioner.yaml` | v1 角色配置文件 |
| 创建 | `prompts/weekly.md` | weekly 命令使用的 prompt 指令模板 |
| 修改 | `scripts/kb.py` | 3处改动：create_raw 加 saved_at、raw 命令加 --saved-at 参数、新增 weekly 命令 |
| 创建 | `tests/test_kb.py` | 验证 saved_at 过滤逻辑和 YAML 解析逻辑 |

---

## Task 1：更新 Raw Schema 模板

**Files:**
- Modify: `templates/raw-note.md`

- [ ] **Step 1：写入新模板**

用以下内容完整替换 `templates/raw-note.md`：

```markdown
---
schema_version: "1"
status: fetched
source_id:
input_type:
source_type:
title:
url:
local_path:
author:
published_at:
saved_at:
fetched_at:
reader:
read_quality:
wiki_targets: []
summary:
key_points: []
confidence: medium
valid_until:
deprecated_reason:
related_raws: []
---

# {{title}}

## Source

- Type:
- URL:
- Local path:
- Author:
- Published:
- Saved:
- Fetched:
- Reader:
- Read quality:

## Original Content

在这里保存原文、转写文本或可追溯摘录。

## Auto Summary（LLM Fixed — 不重新生成）

### 核心观点

### 关键细节

### 事实 / 观点 / 推测

### 限制和不确定性

## Suggestions（LLM Refreshable — 可重新生成）

### 对你的建议

### 是否值得沉淀

### 建议创建或更新的 wiki

## Questions

- 是否发布到 wiki？
- 如果发布，应更新哪篇主题笔记？
```

- [ ] **Step 2：验证文件写入正确**

```bash
head -25 templates/raw-note.md
```

预期输出：前25行包含 `schema_version: "1"` 和 `saved_at:` 字段。

---

## Task 2：更新 Wiki Schema 模板

**Files:**
- Modify: `templates/wiki-note.md`

- [ ] **Step 1：写入新模板**

用以下内容完整替换 `templates/wiki-note.md`：

```markdown
---
schema_version: "1"
status: published
tags: []
sources: []
created_at:
updated_at:
---

# {{topic}}

## 结论

## 适用场景

## 判断依据

每条判断使用以下格式，保证生命周期可追溯：

**判断**：[具体判断内容]
- 置信度：high / medium / low
- 有效期：YYYY-MM
- 来源：raw/xxx.md
- 不确定性：[说明]

过期或被推翻的判断加删除线，不删除：

~~**判断**：[过时内容]~~（已过时：YYYY-MM，原因：[说明]）

## 方法或流程

## 限制

## 来源
```

- [ ] **Step 2：验证**

```bash
head -10 templates/wiki-note.md
```

预期：第一行是 `---`，第二行是 `schema_version: "1"`。

---

## Task 3：创建 Role Profile 配置

**Files:**
- Create: `config/roles/technical_practitioner.yaml`

- [ ] **Step 1：创建目录**

```bash
mkdir -p config/roles
```

- [ ] **Step 2：写入 Role Profile**

创建 `config/roles/technical_practitioner.yaml`：

```yaml
role_id: technical_practitioner
display_name: 技术从业者
focus_areas: [Android, HarmonyOS, Flutter, AI Coding, Engineering Tools, Personal Productivity]
time_window_days: 7
output_template: templates/weekly_technical.md
cold_start_threshold: 5
```

- [ ] **Step 3：验证**

```bash
cat config/roles/technical_practitioner.yaml
```

预期：完整输出6行配置内容。

---

## Task 4：创建 weekly prompt 指令文件

**Files:**
- Create: `prompts/weekly.md`

- [ ] **Step 1：写入 prompt 文件**

创建 `prompts/weekly.md`：

```markdown
# 技术者周报生成指令

你是这个知识库的维护助手，现在需要基于本周已保存的 raw 和现有 wiki，为技术从业者生成一份周报。

## 你的任务

阅读下方提供的 raw 文件和 wiki 上下文，生成一份结构化周报。

## 输出要求

- 每条判断必须关联来源 raw（格式：`raw/filename.md`）
- 区分"有证据的判断"和"待验证的观察"
- 行动建议必须具体可执行，不要泛泛而谈
- 如果某个领域本周没有输入，直接省略该模块，不要凑字数

## 周报结构

```
# YYYY-Www 技术者周报

## 本周输入概览

本周共保存 N 条资料，来自：[来源类型分布]

## GitHub 和工具观察

## 技术判断

格式：
- 结论：
  判断依据：
  来源：raw/xxx.md
  不确定性：
  建议动作：

## 值得试用的项目

## 值得继续编译的主题

## 产品化机会

## 公众号 / 技术文章选题

## 下周行动建议

## 来源索引
```

## 写作原则

- 结论先行，依据跟随
- 不确定的内容必须标注不确定性
- 不要引用没有对应 raw 来源的判断
```

- [ ] **Step 2：验证**

```bash
wc -l prompts/weekly.md
```

预期：行数 > 30。

---

## Task 5：更新 kb.py — 新增 saved_at 支持

**Files:**
- Modify: `scripts/kb.py:259-366`（`create_raw` 函数和 raw 子命令定义）

- [ ] **Step 1：写测试文件，先让测试失败**

创建 `tests/test_kb.py`：

```python
"""Tests for kb.py new functionality."""
import datetime as dt
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "scripts"))
import kb


class TestFrontmatterValue(unittest.TestCase):
    def test_reads_saved_at(self):
        text = "---\nsaved_at: 2026-06-15\nstatus: fetched\n---\n# Title"
        self.assertEqual(kb.frontmatter_value(text, "saved_at"), "2026-06-15")

    def test_missing_field_returns_empty(self):
        text = "---\nstatus: fetched\n---\n# Title"
        self.assertEqual(kb.frontmatter_value(text, "saved_at"), "")


class TestParseSimpleYaml(unittest.TestCase):
    def test_string_value(self):
        result = kb._parse_simple_yaml("role_id: technical_practitioner\n")
        self.assertEqual(result["role_id"], "technical_practitioner")

    def test_int_value(self):
        result = kb._parse_simple_yaml("time_window_days: 7\n")
        self.assertEqual(result["time_window_days"], 7)

    def test_inline_list(self):
        result = kb._parse_simple_yaml("focus_areas: [Android, Flutter, AI Coding]\n")
        self.assertEqual(result["focus_areas"], ["Android", "Flutter", "AI Coding"])

    def test_empty_list(self):
        result = kb._parse_simple_yaml("items: []\n")
        self.assertEqual(result["items"], [])


class TestRawsInWindow(unittest.TestCase):
    def test_filters_by_saved_at(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            # Write a raw that's within the window
            (raw_dir / "recent.md").write_text(
                "---\nsaved_at: 2026-06-20\nstatus: fetched\ntitle: Recent\n---\n",
                encoding="utf-8",
            )
            # Write a raw that's outside the window
            (raw_dir / "old.md").write_text(
                "---\nsaved_at: 2026-01-01\nstatus: fetched\ntitle: Old\n---\n",
                encoding="utf-8",
            )
            cutoff = dt.date(2026, 6, 14)
            results = kb._raws_in_window(raw_dir, cutoff)
            filenames = [p.name for p, _, _ in results]
            self.assertIn("recent.md", filenames)
            self.assertNotIn("old.md", filenames)

    def test_falls_back_to_fetched_at(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            (raw_dir / "no_saved_at.md").write_text(
                "---\nfetched_at: 2026-06-20T10:00:00\nstatus: fetched\ntitle: Test\n---\n",
                encoding="utf-8",
            )
            cutoff = dt.date(2026, 6, 14)
            results = kb._raws_in_window(raw_dir, cutoff)
            self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2：运行测试，确认失败**

```bash
cd /Users/becklong/work/aiWork/karpathy-kb && python3 -m unittest discover tests -v 2>&1 | head -30
```

预期：`AttributeError: module 'kb' has no attribute '_parse_simple_yaml'`，因为函数还不存在。

- [ ] **Step 3：在 kb.py 中添加 `_parse_simple_yaml` 和 `_raws_in_window`**

在 `kb.py` 的 `slugify` 函数之前（约第99行），插入以下两个函数：

```python
def _parse_simple_yaml(text: str) -> dict:
    """Minimal YAML parser for flat key: value structures (no external deps)."""
    result: dict = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            result[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()] if inner else []
        elif value.lstrip("-").isdigit():
            result[key] = int(value)
        else:
            result[key] = value
    return result


def _raws_in_window(
    raw_dir: pathlib.Path, cutoff: dt.date
) -> list[tuple[pathlib.Path, str, dt.date]]:
    """Return raw files whose saved_at (or fetched_at fallback) >= cutoff."""
    results: list[tuple[pathlib.Path, str, dt.date]] = []
    for path in sorted(raw_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        text = read_text(path)
        date_str = frontmatter_value(text, "saved_at") or frontmatter_value(text, "fetched_at")
        if not date_str:
            continue
        try:
            saved_date = dt.date.fromisoformat(date_str[:10])
        except ValueError:
            continue
        if saved_date >= cutoff:
            results.append((path, text, saved_date))
    return results
```

- [ ] **Step 4：运行测试，确认 `_parse_simple_yaml` 和 `_raws_in_window` 测试通过**

```bash
cd /Users/becklong/work/aiWork/karpathy-kb && python3 -m unittest discover tests -v
```

预期：`TestFrontmatterValue`、`TestParseSimpleYaml`、`TestRawsInWindow` 全部 PASS。

- [ ] **Step 5：在 `create_raw()` 中添加 `saved_at` 参数**

修改 `create_raw` 函数签名（约第259行），新增 `saved_at` 参数：

```python
def create_raw(
    source: str,
    title: str | None = None,
    saved_at: str | None = None,          # 新增
    max_chars: int = 24000,
    mode: str = "fast",
    read_depth: str = "standard",
    browser_profile: str = "",
    headless: bool = False,
    interactive_login: bool = False,
    login_timeout_ms: int = 180000,
    service_host: str = DEFAULT_SERVICE_HOST,
    service_port: int = DEFAULT_SERVICE_PORT,
) -> pathlib.Path:
```

- [ ] **Step 6：在 `create_raw()` 内部计算 `saved_at` 并写入 frontmatter**

在 `fetched_at = dt.datetime.now()...` 那行之后（约第287行），添加：

```python
    saved_at_value = saved_at or dt.date.today().isoformat()
```

修改 `body` 字符串中的 frontmatter 部分，将旧的：

```python
    body = f"""---
status: fetched
source_id: {today}-{slugify(final_title)}
input_type: {result.input_type}
source_type: {result.source_type}
title: {final_title}
url: {url}
local_path: {local_path}
author: {result.author}
published_at: {result.published_at}
fetched_at: {fetched_at}
reader: {result.reader}
read_quality: {result.read_quality}
wiki_targets: []
---
```

替换为：

```python
    body = f"""---
schema_version: "1"
status: fetched
source_id: {today}-{slugify(final_title)}
input_type: {result.input_type}
source_type: {result.source_type}
title: {final_title}
url: {url}
local_path: {local_path}
author: {result.author}
published_at: {result.published_at}
saved_at: {saved_at_value}
fetched_at: {fetched_at}
reader: {result.reader}
read_quality: {result.read_quality}
wiki_targets: []
summary:
key_points: []
confidence: medium
valid_until:
deprecated_reason:
related_raws: []
---
```

同时把正文中的 `## Auto Summary` 和 `## Suggestions` 标题更新为：

```python
## Auto Summary（LLM Fixed — 不重新生成）

待 LLM 总结。

## Suggestions（LLM Refreshable — 可重新生成）

待 LLM 结合 profile.md 给出建议。
```

- [ ] **Step 7：在 `raw` 子命令中添加 `--saved-at` 参数**

在 `raw.add_argument("--service-port", ...)` 之后（约第384行），添加：

```python
    raw.add_argument(
        "--saved-at",
        dest="saved_at",
        default=None,
        help="override saved_at date (ISO8601, e.g. 2026-06-01) for backfilling historical raws",
    )
```

- [ ] **Step 8：在 `main()` 的 `raw` 分支中传入 `saved_at`**

修改 `args.command == "raw"` 分支中的 `create_raw(...)` 调用，新增参数：

```python
        target = create_raw(
            args.source,
            args.title,
            saved_at=args.saved_at,    # 新增
            max_chars=args.max_chars,
            mode=args.mode,
            ...
        )
```

- [ ] **Step 9：验证 raw 命令帮助信息包含新参数**

```bash
cd /Users/becklong/work/aiWork/karpathy-kb && python3 scripts/kb.py raw --help
```

预期：输出中包含 `--saved-at`。

---

## Task 6：添加 weekly 命令

**Files:**
- Modify: `scripts/kb.py`（新增 `load_role_profile`、`build_weekly_prompt` 函数，以及 `weekly` 子命令）

- [ ] **Step 1：在 `build_publish_prompt` 之后添加 `load_role_profile` 和 `build_weekly_prompt`**

在 `build_publish_prompt` 函数（约第240行）之后，插入：

```python
def load_role_profile(role_id: str) -> dict:
    config_path = ROOT / "config" / "roles" / f"{role_id}.yaml"
    if not config_path.exists():
        raise SystemExit(f"role profile not found: {config_path}")
    return _parse_simple_yaml(config_path.read_text(encoding="utf-8"))


def build_weekly_prompt(role_id: str = "technical_practitioner") -> str:
    profile = load_role_profile(role_id)
    time_window = int(profile.get("time_window_days", 7))
    threshold = int(profile.get("cold_start_threshold", 5))
    focus_areas = profile.get("focus_areas", [])
    if isinstance(focus_areas, str):
        focus_areas = [focus_areas]

    today = dt.date.today()
    cutoff = today - dt.timedelta(days=time_window)
    week_label = today.strftime("%Y-W%W")

    raw_dir = _require_raw_dir()
    raws = _raws_in_window(raw_dir, cutoff)

    cold_start_warning = ""
    if len(raws) < threshold:
        cold_start_warning = (
            f"\n> ⚠ 本周输入偏少（{len(raws)} 条，建议 {threshold}+ 条），"
            "以下判断仅供参考，建议补充更多资料后重新生成。\n"
        )

    raws_section = ""
    for path, text, saved_date in sorted(raws, key=lambda x: x[2]):
        raws_section += f"\n---\n### {path.name} (saved: {saved_date})\n\n{text}\n"

    wiki_dir = ROOT / "wiki"
    wiki_section = ""
    if wiki_dir.exists():
        for path in sorted(wiki_dir.glob("*.md")):
            if path.name == "README.md":
                continue
            wiki_section += f"\n---\n### wiki/{path.name}\n\n{read_text(path)}\n"

    weekly_instructions = ""
    instructions_path = ROOT / "prompts" / "weekly.md"
    if instructions_path.exists():
        weekly_instructions = read_text(instructions_path)

    focus_str = "、".join(focus_areas) if focus_areas else "技术领域"

    return f"""# 生成 {week_label} 技术者周报

{cold_start_warning}
## 用户 Profile

{read_text(PROFILE)}

## 角色关注领域

{focus_str}

## 周报生成指令

{weekly_instructions}

## 本周 Raw 资料（{cutoff} 至 {today}，共 {len(raws)} 条）

{raws_section if raws_section else "（本周无 raw 资料）"}

## Wiki 长期知识上下文

{wiki_section if wiki_section else "（暂无 wiki 内容）"}

## 输出目标

请生成 `reviews/{week_label}.md` 的内容。直接输出 Markdown 正文，不需要额外说明。
"""
```

- [ ] **Step 2：在 `main()` 的 `sub` 中注册 `weekly` 子命令**

在 `publish = sub.add_parser(...)` 之后（约第391行），添加：

```python
    weekly = sub.add_parser("weekly", help="generate weekly report prompt")
    weekly.add_argument("--role", default="technical_practitioner", help="role profile id")
```

- [ ] **Step 3：在 `main()` 的分支中处理 `weekly`**

在 `if args.command == "publish-prompt":` 块之后，添加：

```python
    if args.command == "weekly":
        print(build_weekly_prompt(args.role))
        return 0
```

- [ ] **Step 4：运行所有测试**

```bash
cd /Users/becklong/work/aiWork/karpathy-kb && python3 -m unittest discover tests -v
```

预期：全部 PASS，无 ERROR 或 FAIL。

- [ ] **Step 5：验证 weekly 命令注册正确**

```bash
cd /Users/becklong/work/aiWork/karpathy-kb && python3 scripts/kb.py weekly --help
```

预期：输出包含 `--role`。

- [ ] **Step 6：冒烟测试 weekly 命令**

```bash
cd /Users/becklong/work/aiWork/karpathy-kb && python3 scripts/kb.py weekly 2>&1 | head -20
```

预期：输出第一行为 `# 生成 2026-W... 技术者周报`，无报错。

---

## 自检清单

- [ ] `templates/raw-note.md` 包含 `schema_version`, `saved_at`, `confidence`, `valid_until`, `deprecated_reason`, `related_raws`
- [ ] `templates/wiki-note.md` 包含 `schema_version`, `created_at`，正文有判断条目格式说明
- [ ] `config/roles/technical_practitioner.yaml` 存在且包含 `time_window_days` 和 `cold_start_threshold`
- [ ] `prompts/weekly.md` 存在且包含周报结构模板
- [ ] `kb.py raw --help` 显示 `--saved-at`
- [ ] `kb.py weekly --help` 显示 `--role`
- [ ] 所有测试 PASS
- [ ] `kb.py weekly` 冒烟测试无报错
