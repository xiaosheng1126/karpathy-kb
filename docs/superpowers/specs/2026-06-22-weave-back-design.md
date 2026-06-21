# Weave-Back (往回织) v2a Design Spec

**Goal:** When generating a publish prompt, automatically scan `wiki_targets` from the raw's frontmatter, match against existing wiki titles, and surface which wikis need updating and which topics have no wiki yet.

**Scope:** `scripts/kb.py` only. No new commands. No LLM calls. No Schema changes.

---

## Trigger Point

Integrated into `build_publish_prompt(raw_path)`. Runs every time the user generates a publish prompt. No separate command needed.

## New Functions

### `frontmatter_list_value(text: str, key: str) -> list[str]`

Reads an inline YAML list from frontmatter. Handles:
- `wiki_targets: [代理工具, TUN模式]` → `["代理工具", "TUN模式"]`
- `wiki_targets: []` → `[]`
- Missing key → `[]`

Uses the same inline-list parsing logic already in `_parse_simple_yaml`.

### `find_matching_wikis(targets: list[str], wiki_dir: Path) -> tuple[list[tuple[str, Path, str]], list[str]]`

Returns `(matched, unmatched)`:
- `matched`: list of `(target, wiki_path, wiki_title)` — for each target that is a case-insensitive substring of any wiki's H1 title
- `unmatched`: list of targets with no match

Scan logic:
1. Glob `wiki_dir/*.md`, skip `README.md`
2. For each wiki file, extract H1 title: first line starting with `# `
3. For each target, check `target.lower() in title.lower()`
4. A target can match multiple wikis (all matches included)

## Changes to `build_publish_prompt()`

After existing content, append a weave-back block if `wiki_targets` is non-empty:

```
## 往回织提示（Weave-Back）

以下已有 wiki 与 wiki_targets 匹配，发布时请检查是否需要更新：

- wiki/foo.md（《标题》）→ 目标：代理工具

以下 wiki_targets 尚无对应 wiki，建议新建：

- AI编程
```

Edge cases:
- `wiki_targets: []` → skip entire block
- All targets matched → omit "建议新建" section
- No wikis in `wiki/` → all targets go to "建议新建"

## Tests

Add to `tests/test_kb.py`:

**`TestFrontmatterListValue`**
- `test_reads_wiki_targets`: inline list with values → correct list returned
- `test_empty_list`: `wiki_targets: []` → `[]`

**`TestFindMatchingWikis`**
- `test_matched`: wiki title contains target (case-insensitive) → appears in matched
- `test_unmatched`: no wiki title contains target → appears in unmatched
- `test_empty_targets`: targets=`[]` → `([], [])`

All tests use `tempfile.TemporaryDirectory` for wiki files. No real filesystem dependency.

## Out of Scope

- Fuzzy matching / edit distance (v3+, when wiki count justifies it)
- Tag-based matching (v3+, when tags are populated)
- Updating wiki files automatically (requires user confirmation, not automated)
- New CLI command (intentionally avoided to keep UX simple)
