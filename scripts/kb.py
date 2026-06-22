#!/usr/bin/env python3
"""
Small helper for the Obsidian knowledge base.

This script is intentionally mechanical. It creates a raw draft by calling the
local source-reader HTTP service; the LLM still owns summary, advice, and wiki
publication decisions.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request


DEFAULT_SERVICE_HOST = "127.0.0.1"
DEFAULT_SERVICE_PORT = 8765

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "prompts"
PROFILE = ROOT / "profile.md"

_config_file = ROOT / "config.json"
_config: dict = json.loads(_config_file.read_text(encoding="utf-8")) if _config_file.exists() else {}

_OBSIDIAN_CANDIDATES = [
    pathlib.Path("~/Documents/Obsidian Vault").expanduser(),
    pathlib.Path("~/Documents/Obsidian").expanduser(),
    pathlib.Path("~/Obsidian").expanduser(),
]


def _resolve_raw_dir() -> "pathlib.Path | None":
    if "raw_dir" in _config:
        return pathlib.Path(_config["raw_dir"]).expanduser()
    for candidate in _OBSIDIAN_CANDIDATES:
        if candidate.is_dir():
            inbox = candidate / "00_Inbox"
            return inbox if inbox.is_dir() else candidate
    return None


RAW_DIR = _resolve_raw_dir()

_RAW_DIR_HINT = (
    "未找到 Obsidian vault，raw_dir 未配置。\n"
    "请在知识库根目录创建 config.json：\n"
    '{\n  "raw_dir": "~/Documents/Obsidian Vault/00_Inbox"\n}'
)


def _require_raw_dir() -> pathlib.Path:
    if RAW_DIR is None:
        raise SystemExit(_RAW_DIR_HINT)
    return RAW_DIR


@dataclasses.dataclass
class ReaderOutput:
    input_type: str = ""
    source_type: str = ""
    title: str = ""
    url: str = ""
    local_path: str = ""
    author: str = ""
    published_at: str = ""
    reader: str = ""
    read_quality: str = ""
    strategy: str = ""
    token_policy: str = ""
    read_depth: str = ""
    content: str = ""
    preview: dict = dataclasses.field(default_factory=dict)
    actions: list = dataclasses.field(default_factory=list)
    next_actions: list = dataclasses.field(default_factory=list)
    metadata: dict = dataclasses.field(default_factory=dict)
    errors: list = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ReaderOutput":
        fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in fields})


def display_path(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9一-鿿]+", "-", value)
    value = value.strip("-")
    return value[:48] or "untitled"


def json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def service_url(host: str, port: int, path: str) -> str:
    return f"http://{host}:{port}{path}"


def post_json(url: str, payload: dict, timeout: int = 300) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decoded = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"source-reader service unreachable at {url}: {exc}.\n"
            "Start it from the standalone repo, e.g.:\n"
            "  cd ~/Documents/source-reader && python3 scripts/source_reader.py serve --host 127.0.0.1 --port 8765"
        ) from exc
    parsed = json.loads(decoded)
    if not isinstance(parsed, dict):
        raise SystemExit("source-reader service returned non-object json")
    if parsed.get("ok") is False:
        raise SystemExit(str(parsed.get("error") or "source-reader service failed"))
    return parsed


def read_via_service(
    source: str,
    host: str,
    port: int,
    max_chars: int,
    mode: str,
    read_depth: str,
    browser_profile: str,
    headless: bool,
    interactive_login: bool,
    login_timeout_ms: int,
) -> ReaderOutput:
    response = post_json(
        service_url(host, port, "/read"),
        {
            "source": source,
            "max_chars": max_chars,
            "mode": mode,
            "read_depth": read_depth,
            "browser_profile": browser_profile,
            "headless": headless,
            "interactive_login": interactive_login,
            "login_timeout_ms": login_timeout_ms,
        },
    )
    result = response.get("result")
    if not isinstance(result, dict):
        raise SystemExit("source-reader service response missing result")
    return ReaderOutput.from_dict(result)


def resolve_raw(path_text: str | None = None) -> pathlib.Path:
    if path_text:
        candidate = pathlib.Path(path_text).expanduser()
        if not candidate.is_absolute():
            candidate = (ROOT / candidate).resolve()
        if not candidate.exists():
            raise SystemExit(f"raw file does not exist: {candidate}")
        if not candidate.is_file():
            raise SystemExit(f"not a file: {candidate}")
        return candidate

    raw_files = sorted(_require_raw_dir().glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    raw_files = [path for path in raw_files if path.name != "README.md"]
    if not raw_files:
        raise SystemExit("no raw files found")
    return raw_files[0]


def frontmatter_value(text: str, key: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    frontmatter = text[3:end].splitlines()
    prefix = f"{key}:"
    for line in frontmatter:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def frontmatter_list_value(text: str, key: str) -> list[str]:
    raw = frontmatter_value(text, key)
    if not raw or not raw.startswith("["):
        return []
    inner = raw[1:-1].strip() if raw.endswith("]") else ""
    if not inner:
        return []
    return [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]


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


def list_raw(status: str | None = None) -> list[tuple[pathlib.Path, str, str]]:
    rows: list[tuple[pathlib.Path, str, str]] = []
    for path in sorted(_require_raw_dir().glob("*.md")):
        if path.name == "README.md":
            continue
        text = read_text(path)
        raw_status = frontmatter_value(text, "status") or "unknown"
        title = frontmatter_value(text, "title") or path.stem
        if status and raw_status != status:
            continue
        rows.append((path, raw_status, title))
    return rows


def build_review_prompt(raw_path: pathlib.Path) -> str:
    return f"""# Review This Raw Note

你现在是这个 Obsidian 知识库的维护助手。请审阅 raw，但不要更新 wiki，也不要把 reviewed/approved 写入文件。

## User Profile

{read_text(PROFILE)}

## Review Rules

{read_text(PROMPTS_DIR / "raw-review.md")}

## Raw Note

{read_text(raw_path)}
"""


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


def create_raw(
    source: str,
    title: str | None = None,
    saved_at: str | None = None,
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
    result = read_via_service(
        source,
        service_host,
        service_port,
        max_chars,
        mode,
        read_depth,
        browser_profile or ".source-reader/profiles/default",
        headless,
        interactive_login,
        login_timeout_ms,
    )
    is_url = bool(result.url)
    final_title = title or result.title
    today = dt.date.today().isoformat()
    fetched_at = dt.datetime.now().isoformat(timespec="seconds")
    saved_at_value = saved_at or dt.date.today().isoformat()
    filename = f"{today}-{slugify(final_title)}.md"
    target = _require_raw_dir() / filename

    if target.exists():
        raise SystemExit(f"raw file already exists: {target}")

    url = result.url if is_url else ""
    local_path = result.local_path
    preview = result.content if result.content else "读取结果为空。"
    metadata = {
        "source_type": result.source_type,
        "strategy": result.strategy,
        "token_policy": result.token_policy,
        "read_depth": result.read_depth,
        "preview": result.preview,
        "actions": result.actions,
        "next_actions": result.next_actions,
        "metadata": result.metadata,
        "errors": result.errors,
    }

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

# {final_title}

## Source

- Type: {result.input_type}
- Source type: {result.source_type}
- URL: {url}
- Local path: {local_path}
- Author: {result.author}
- Published: {result.published_at}
- Fetched: {fetched_at}
- Reader: {result.reader}
- Read quality: {result.read_quality}
- Strategy: {result.strategy}
- Token policy: {result.token_policy}
- Read depth: {result.read_depth}

## Reader Metadata

```json
{json_dumps(metadata)}
```

## Original Content

{preview}

## Auto Summary（LLM Fixed — 不重新生成）

待 LLM 总结。

## Suggestions（LLM Refreshable — 可重新生成）

待 LLM 结合 profile.md 给出建议。

## Questions

- 是否发布到 wiki？
- 如果发布，应更新哪篇主题笔记？
"""
    target.write_text(body, encoding="utf-8")
    return target


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Karpathy KB helper")
    sub = parser.add_subparsers(dest="command", required=True)

    raw = sub.add_parser("raw", help="create a raw draft from a source")
    raw.add_argument("source", help="URL or local file path")
    raw.add_argument("--title", help="override title")
    raw.add_argument("--max-chars", type=int, default=24000, help="maximum original content characters to store")
    raw.add_argument("--mode", choices=["fast", "browser", "auto"], default="fast", help="source-reader mode")
    raw.add_argument("--read-depth", choices=["preview", "standard", "full"], default="standard", help="source-reader reading depth")
    raw.add_argument("--browser-profile", default="", help="persistent browser profile directory for browser/auto mode")
    raw.add_argument("--headless", action="store_true", help="run browser mode headless")
    raw.add_argument("--interactive-login", action="store_true", help="wait for manual login when browser mode reaches an auth page")
    raw.add_argument("--login-timeout-ms", type=int, default=180000, help="manual login wait timeout in milliseconds")
    raw.add_argument("--service-host", default=DEFAULT_SERVICE_HOST, help="source-reader service host")
    raw.add_argument("--service-port", type=int, default=DEFAULT_SERVICE_PORT, help="source-reader service port")
    raw.add_argument(
        "--saved-at",
        dest="saved_at",
        default=None,
        help="override saved_at date (ISO8601, e.g. 2026-06-01) for backfilling historical raws",
    )

    list_cmd = sub.add_parser("list", help="list raw notes")
    list_cmd.add_argument("--status", help="filter by raw status, for example fetched")

    review = sub.add_parser("review", help="print a review prompt for a raw note")
    review.add_argument("raw_file", nargs="?", help="raw note path; defaults to latest raw")

    publish = sub.add_parser("publish-prompt", help="print a publish prompt for a raw note")
    publish.add_argument("raw_file", nargs="?", help="raw note path; defaults to latest raw")

    weekly = sub.add_parser("weekly", help="generate weekly report prompt")
    weekly.add_argument("--role", default="technical_practitioner", help="role profile id")

    args = parser.parse_args(argv)

    if args.command == "raw":
        target = create_raw(
            args.source,
            args.title,
            saved_at=args.saved_at,
            max_chars=args.max_chars,
            mode=args.mode,
            read_depth=args.read_depth,
            browser_profile=args.browser_profile,
            headless=args.headless,
            interactive_login=args.interactive_login,
            login_timeout_ms=args.login_timeout_ms,
            service_host=args.service_host,
            service_port=args.service_port,
        )
        print(display_path(target))
        return 0

    if args.command == "list":
        rows = list_raw(args.status)
        if not rows:
            return 0
        for path, raw_status, title in rows:
            print(f"{raw_status}\t{display_path(path)}\t{title}")
        return 0

    if args.command == "review":
        raw_path = resolve_raw(args.raw_file)
        print(build_review_prompt(raw_path))
        return 0

    if args.command == "publish-prompt":
        raw_path = resolve_raw(args.raw_file)
        print(build_publish_prompt(raw_path))
        return 0

    if args.command == "weekly":
        print(build_weekly_prompt(args.role))
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
