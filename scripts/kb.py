#!/usr/bin/env python3
"""
Small helper for the Obsidian knowledge base.

This script is intentionally mechanical. It can create a raw draft from a
local file or a simple URL, but the LLM still owns summary, advice, and wiki
publication decisions.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html.parser
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

from source_reader import classify_and_read


ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"
PROMPTS_DIR = ROOT / "prompts"
PROFILE = ROOT / "profile.md"


class TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "br", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title += text
        if not self._skip:
            self.parts.append(text)

    def text(self) -> str:
        raw = " ".join(self.parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    value = value.strip("-")
    return value[:48] or "untitled"


def json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def read_url(url: str) -> tuple[str, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 kb-source-reader/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content_type = response.headers.get("content-type", "")
            body = response.read()
    except urllib.error.URLError as exc:
        raise SystemExit(f"failed to read URL: {exc}") from exc

    charset_match = re.search(r"charset=([\w-]+)", content_type)
    charset = charset_match.group(1) if charset_match else "utf-8"
    decoded = body.decode(charset, errors="replace")

    if "html" in content_type or decoded.lstrip().startswith("<"):
        extractor = TextExtractor()
        extractor.feed(decoded)
        title = extractor.title.strip() or url
        return title, extractor.text(), "url"

    return url, decoded.strip(), "url"


def read_file(path_text: str) -> tuple[str, str, str]:
    path = pathlib.Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"file does not exist: {path}")
    if not path.is_file():
        raise SystemExit(f"not a file: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    return path.stem, text.strip(), "file"


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


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

    raw_files = sorted(RAW_DIR.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
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


def list_raw(status: str | None = None) -> list[tuple[pathlib.Path, str, str]]:
    rows: list[tuple[pathlib.Path, str, str]] = []
    for path in sorted(RAW_DIR.glob("*.md")):
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


def create_raw(
    source: str,
    title: str | None = None,
    max_chars: int = 24000,
    mode: str = "fast",
    read_depth: str = "standard",
    browser_profile: str = "",
    headless: bool = False,
    interactive_login: bool = False,
    login_timeout_ms: int = 180000,
) -> pathlib.Path:
    result = classify_and_read(
        source,
        max_chars=max_chars,
        mode=mode,
        browser_profile=browser_profile,
        headless=headless,
        interactive_login=interactive_login,
        login_timeout_ms=login_timeout_ms,
        read_depth=read_depth,
    )
    is_url = bool(result.url)
    final_title = title or result.title
    today = dt.date.today().isoformat()
    fetched_at = dt.datetime.now().isoformat(timespec="seconds")
    filename = f"{today}-{slugify(final_title)}.md"
    target = RAW_DIR / filename

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
        "next_actions": result.next_actions,
        "metadata": result.metadata,
        "errors": result.errors,
    }

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

## Auto Summary

待 LLM 总结。

## Suggestions

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

    list_cmd = sub.add_parser("list", help="list raw notes")
    list_cmd.add_argument("--status", help="filter by raw status, for example fetched")

    review = sub.add_parser("review", help="print a review prompt for a raw note")
    review.add_argument("raw_file", nargs="?", help="raw note path; defaults to latest raw")

    publish = sub.add_parser("publish-prompt", help="print a publish prompt for a raw note")
    publish.add_argument("raw_file", nargs="?", help="raw note path; defaults to latest raw")

    args = parser.parse_args(argv)

    if args.command == "raw":
        target = create_raw(
            args.source,
            args.title,
            args.max_chars,
            mode=args.mode,
            read_depth=args.read_depth,
            browser_profile=args.browser_profile,
            headless=args.headless,
            interactive_login=args.interactive_login,
            login_timeout_ms=args.login_timeout_ms,
        )
        print(target.relative_to(ROOT))
        return 0

    if args.command == "list":
        rows = list_raw(args.status)
        if not rows:
            return 0
        for path, raw_status, title in rows:
            print(f"{raw_status}\t{path.relative_to(ROOT)}\t{title}")
        return 0

    if args.command == "review":
        raw_path = resolve_raw(args.raw_file)
        print(build_review_prompt(raw_path))
        return 0

    if args.command == "publish-prompt":
        raw_path = resolve_raw(args.raw_file)
        print(build_publish_prompt(raw_path))
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
