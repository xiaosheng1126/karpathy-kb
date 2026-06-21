# Weave-Back v2a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate wiki_targets matching into `build_publish_prompt()` so that every publish prompt surfaces which existing wikis need updating and which topics have no wiki yet.

**Architecture:** Two new pure functions (`frontmatter_list_value`, `find_matching_wikis`) added to `scripts/kb.py`, then wired into `build_publish_prompt()`. No new commands, no LLM calls, no Schema changes.

**Tech Stack:** Python 3.11+ stdlib only. Test runner: `python3 -m unittest discover tests -v`.

---

## Context for implementors

**Repo layout (relevant paths):**
```
scripts/kb.py         # all logic lives here
tests/test_kb.py      # existing tests, add new classes here
wiki/                 # *.md files with H1 titles, skip README.md
```

**Key existing functions in `scripts/kb.py`:**

`frontmatter_value(text, key) -> str` (line 236) — reads a scalar value from YAML frontmatter between `---` markers. Returns `""` if missing.

`read_text(path) -> str` (line ~85) — reads a file, returns `""` if missing.

`ROOT` (line ~60) — `pathlib.Path` pointing to repo root (parent of `scripts/`).

**`build_publish_prompt()` current body (lines 283–299):**
```python
def build_publish_prompt(raw_path: pathlib.Path) -> str:
    return f"""# Publish This Raw Note

用户已经明确确认可以发布。请基于 raw 更新 wiki、index 和 log，并把 raw status 改为 published。

## User Profile

{read_text(PROFILE)}

## Publish Rules

{read_text(PROMPTS_DIR / "publish.md")}

## Raw Note

{read_text(raw_path)}
"""
```

**Inline list format in raw frontmatter:**
```
wiki_targets: [代理工具, TUN模式]   # non-empty
wiki_targets: []                    # empty
```

**Run tests with:**
```bash
python3 -m unittest discover tests -v
```

---

## Task 1: `frontmatter_list_value()`

**Files:**
- Modify: `scripts/kb.py` — insert after line 247 (after `frontmatter_value`)
- Modify: `tests/test_kb.py` — add `TestFrontmatterListValue` class

- [ ] **Step 1: Write the failing tests**

Add this class to `tests/test_kb.py` before the `if __name__ == "__main__":` line:

```python
class TestFrontmatterListValue(unittest.TestCase):
    def test_reads_wiki_targets(self):
        text = "---\nwiki_targets: [代理工具, TUN模式]\nstatus: fetched\n---\n# Title"
        result = kb.frontmatter_list_value(text, "wiki_targets")
        self.assertEqual(result, ["代理工具", "TUN模式"])

    def test_empty_list(self):
        text = "---\nwiki_targets: []\nstatus: fetched\n---\n# Title"
        result = kb.frontmatter_list_value(text, "wiki_targets")
        self.assertEqual(result, [])

    def test_missing_key_returns_empty(self):
        text = "---\nstatus: fetched\n---\n# Title"
        result = kb.frontmatter_list_value(text, "wiki_targets")
        self.assertEqual(result, [])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m unittest discover tests -v
```

Expected: 3 new tests FAIL with `AttributeError: module 'kb' has no attribute 'frontmatter_list_value'`

- [ ] **Step 3: Implement `frontmatter_list_value()`**

In `scripts/kb.py`, insert this function immediately after `frontmatter_value()` (after line 247, before `list_raw`):

```python
def frontmatter_list_value(text: str, key: str) -> list[str]:
    raw = frontmatter_value(text, key)
    if not raw or not raw.startswith("["):
        return []
    inner = raw[1:-1].strip() if raw.endswith("]") else ""
    if not inner:
        return []
    return [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m unittest discover tests -v
```

Expected: all tests PASS (existing 8 + new 3 = 11 total)

- [ ] **Step 5: Commit**

```bash
git add scripts/kb.py tests/test_kb.py
git commit -m "feat(v2a): add frontmatter_list_value() for inline list parsing"
```

---

## Task 2: `find_matching_wikis()`

**Files:**
- Modify: `scripts/kb.py` — insert after `frontmatter_list_value()`
- Modify: `tests/test_kb.py` — add `TestFindMatchingWikis` class

- [ ] **Step 1: Write the failing tests**

Add this class to `tests/test_kb.py` before the `if __name__ == "__main__":` line:

```python
class TestFindMatchingWikis(unittest.TestCase):
    def test_matched(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "proxy.md").write_text(
                "# 代理工具 TUN 模式下国内网站断网问题\n\n内容",
                encoding="utf-8",
            )
            matched, unmatched = kb.find_matching_wikis(["代理工具"], wiki_dir)
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0][0], "代理工具")
            self.assertIn("代理工具", matched[0][2])
            self.assertEqual(unmatched, [])

    def test_matched_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "flutter.md").write_text(
                "# Flutter 状态管理对比\n\n内容",
                encoding="utf-8",
            )
            matched, unmatched = kb.find_matching_wikis(["flutter"], wiki_dir)
            self.assertEqual(len(matched), 1)
            self.assertEqual(unmatched, [])

    def test_unmatched(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "proxy.md").write_text(
                "# 代理工具 TUN 模式\n\n内容",
                encoding="utf-8",
            )
            matched, unmatched = kb.find_matching_wikis(["Flutter"], wiki_dir)
            self.assertEqual(matched, [])
            self.assertEqual(unmatched, ["Flutter"])

    def test_empty_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            matched, unmatched = kb.find_matching_wikis([], wiki_dir)
            self.assertEqual(matched, [])
            self.assertEqual(unmatched, [])

    def test_skips_readme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "README.md").write_text("# README\n\n内容", encoding="utf-8")
            matched, unmatched = kb.find_matching_wikis(["README"], wiki_dir)
            self.assertEqual(matched, [])
            self.assertEqual(unmatched, ["README"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m unittest discover tests -v
```

Expected: 5 new tests FAIL with `AttributeError: module 'kb' has no attribute 'find_matching_wikis'`

- [ ] **Step 3: Implement `find_matching_wikis()`**

In `scripts/kb.py`, insert this function immediately after `frontmatter_list_value()`:

```python
def find_matching_wikis(
    targets: list[str],
    wiki_dir: pathlib.Path,
) -> tuple[list[tuple[str, pathlib.Path, str]], list[str]]:
    wiki_titles: list[tuple[pathlib.Path, str]] = []
    if wiki_dir.exists():
        for path in sorted(wiki_dir.glob("*.md")):
            if path.name == "README.md":
                continue
            text = read_text(path)
            for line in text.splitlines():
                if line.startswith("# "):
                    wiki_titles.append((path, line[2:].strip()))
                    break

    matched: list[tuple[str, pathlib.Path, str]] = []
    unmatched: list[str] = []
    for target in targets:
        hits = [
            (target, p, title)
            for p, title in wiki_titles
            if target.lower() in title.lower()
        ]
        if hits:
            matched.extend(hits)
        else:
            unmatched.append(target)

    return matched, unmatched
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m unittest discover tests -v
```

Expected: all tests PASS (11 existing + 5 new = 16 total)

- [ ] **Step 5: Commit**

```bash
git add scripts/kb.py tests/test_kb.py
git commit -m "feat(v2a): add find_matching_wikis() with H1 title substring matching"
```

---

## Task 3: Wire into `build_publish_prompt()`

**Files:**
- Modify: `scripts/kb.py` — replace `build_publish_prompt()` body (lines 283–299)

No new tests needed: `frontmatter_list_value` and `find_matching_wikis` are fully tested. This task is pure wiring — verify manually with a smoke run.

- [ ] **Step 1: Replace `build_publish_prompt()` body**

Replace the entire function (currently lines 283–299) with:

```python
def build_publish_prompt(raw_path: pathlib.Path) -> str:
    raw_text = read_text(raw_path)
    targets = frontmatter_list_value(raw_text, "wiki_targets")

    weave_back_block = ""
    if targets:
        matched, unmatched = find_matching_wikis(targets, ROOT / "wiki")
        lines: list[str] = ["", "## 往回织提示（Weave-Back）", ""]
        if matched:
            lines.append("以下已有 wiki 与 wiki_targets 匹配，发布时请检查是否需要更新：")
            lines.append("")
            for target, path, title in matched:
                rel = path.relative_to(ROOT)
                lines.append(f"- {rel}（《{title}》）→ 目标：{target}")
        if unmatched:
            lines.append("")
            lines.append("以下 wiki_targets 尚无对应 wiki，建议新建：")
            lines.append("")
            for t in unmatched:
                lines.append(f"- {t}")
        weave_back_block = "\n".join(lines)

    return f"""# Publish This Raw Note

用户已经明确确认可以发布。请基于 raw 更新 wiki、index 和 log，并把 raw status 改为 published。

## User Profile

{read_text(PROFILE)}

## Publish Rules

{read_text(PROMPTS_DIR / "publish.md")}

## Raw Note

{raw_text}{weave_back_block}
"""
```

- [ ] **Step 2: Run existing tests to confirm no regression**

```bash
python3 -m unittest discover tests -v
```

Expected: all 16 tests PASS

- [ ] **Step 3: Smoke test with the real wiki file**

The repo has `wiki/proxy-tun-fakeip-cn-bypass.md` with title `# 代理工具 TUN 模式下国内网站断网问题`.

Create a temporary raw file to test against:

```bash
python3 - <<'EOF'
import pathlib, sys
sys.path.insert(0, "scripts")
import kb

# Create a minimal raw with wiki_targets that should match the existing wiki
raw = pathlib.Path("/tmp/test_raw.md")
raw.write_text(
    "---\nwiki_targets: [代理工具, Flutter]\nstatus: fetched\ntitle: Test\n---\n# Test\n",
    encoding="utf-8",
)
prompt = kb.build_publish_prompt(raw)
# Print only the weave-back section
start = prompt.find("## 往回织")
print(prompt[start:] if start != -1 else "(no weave-back block — check wiki_targets parsing)")
EOF
```

Expected output:
```
## 往回织提示（Weave-Back）

以下已有 wiki 与 wiki_targets 匹配，发布时请检查是否需要更新：

- wiki/proxy-tun-fakeip-cn-bypass.md（《代理工具 TUN 模式下国内网站断网问题》）→ 目标：代理工具

以下 wiki_targets 尚无对应 wiki，建议新建：

- Flutter
```

- [ ] **Step 4: Commit**

```bash
git add scripts/kb.py
git commit -m "feat(v2a): wire weave-back into build_publish_prompt()

Appends 往回织提示 block showing matched wikis and missing topics.
Block is omitted when wiki_targets is empty."
```
