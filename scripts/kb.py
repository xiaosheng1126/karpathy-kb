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


def slugify_topic(topic: str) -> str:
    """Convert a wiki topic name to a filename slug."""
    value = topic.strip().lower()
    value = re.sub(r"[^a-z0-9一-鿿]+", "-", value)
    return value.strip("-")[:48] or "untitled"


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


def _parse_valid_until(date_str: str) -> "dt.date | None":
    if not date_str:
        return None
    try:
        if len(date_str) == 7:
            return dt.date.fromisoformat(date_str + "-01")
        return dt.date.fromisoformat(date_str[:10])
    except ValueError:
        return None


def raw_aging_status(
    text: str,
    today: dt.date,
    threshold_days: int = 30,
) -> str:
    """Return aging status string for a raw note's text.

    Returns one of: "expired", "aging", "active", "-" (no valid_until).
    """
    date_str = frontmatter_value(text, "valid_until")
    valid_until = _parse_valid_until(date_str)
    if valid_until is None:
        return "-"
    days_diff = (valid_until - today).days
    if days_diff < 0:
        return "expired"
    if days_diff <= threshold_days:
        return "aging"
    return "active"


@dataclasses.dataclass
class AgingEntry:
    file: pathlib.Path
    kind: str          # "raw" | "wiki_judgment"
    label: str         # title for raw, judgment statement for wiki
    valid_until: dt.date
    status: str        # "expired" | "aging"
    days_diff: int     # negative = days past expiry, positive = days until expiry


def scan_aging_raws(
    raw_dir: pathlib.Path,
    today: dt.date,
    aging_threshold_days: int = 30,
) -> list[AgingEntry]:
    entries: list[AgingEntry] = []
    for path in sorted(raw_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        text = read_text(path)
        valid_until = _parse_valid_until(frontmatter_value(text, "valid_until"))
        if valid_until is None:
            continue
        days_diff = (valid_until - today).days
        if days_diff < 0:
            status = "expired"
        elif days_diff <= aging_threshold_days:
            status = "aging"
        else:
            continue
        label = frontmatter_value(text, "title") or path.stem
        entries.append(AgingEntry(path, "raw", label, valid_until, status, days_diff))
    return entries


def scan_aging_wikis(
    wiki_dir: pathlib.Path,
    today: dt.date,
    aging_threshold_days: int = 30,
) -> list[AgingEntry]:
    entries: list[AgingEntry] = []
    if not wiki_dir.exists():
        return entries
    for path in sorted(wiki_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        text = read_text(path)
        current_judgment: str | None = None
        for line in text.splitlines():
            if line.startswith("**判断**：") or line.startswith("**判断**:"):
                stmt = re.split("[：:]", line, maxsplit=1)[-1].strip()
                if "~~" in stmt:
                    current_judgment = None
                    continue
                current_judgment = re.sub(r"~~(.+?)~~", r"\1", stmt).rstrip("。.")
            m = re.match(r"\s*[-*]\s*有效期[：:]\s*(\d{4}-\d{2}(?:-\d{2})?)", line)
            if m and current_judgment is not None:
                valid_until = _parse_valid_until(m.group(1))
                if valid_until is None:
                    current_judgment = None
                    continue
                days_diff = (valid_until - today).days
                if days_diff < 0:
                    status = "expired"
                elif days_diff <= aging_threshold_days:
                    status = "aging"
                else:
                    current_judgment = None
                    continue
                entries.append(AgingEntry(path, "wiki_judgment", current_judgment, valid_until, status, days_diff))
                current_judgment = None
    return entries


def build_aging_report(
    raw_entries: list[AgingEntry],
    wiki_entries: list[AgingEntry],
    today: dt.date,
) -> str:
    def days_label(e: AgingEntry) -> str:
        if e.status == "expired":
            return f"已过期 {-e.days_diff} 天"
        return f"还剩 {e.days_diff} 天"

    lines: list[str] = [f"# Aging Report ({today})", ""]

    lines.append("## Raw 条目")
    lines.append("")
    if raw_entries:
        for e in raw_entries:
            tag = "EXPIRED" if e.status == "expired" else "AGING  "
            lines.append(f"- [{tag}] `{display_path(e.file)}` — {e.label}（有效期: {e.valid_until}, {days_label(e)}）")
    else:
        lines.append("无到期或即将到期条目。")
    lines.append("")

    lines.append("## Wiki 判断")
    lines.append("")
    if wiki_entries:
        for e in wiki_entries:
            tag = "EXPIRED" if e.status == "expired" else "AGING  "
            lines.append(f"- [{tag}] `{display_path(e.file)}` — {e.label}（有效期: {e.valid_until}, {days_label(e)}）")
    else:
        lines.append("无到期或即将到期判断。")
    lines.append("")

    return "\n".join(lines)


def build_aging_block(
    raw_entries: list[AgingEntry],
    wiki_entries: list[AgingEntry],
) -> str:
    all_entries = raw_entries + wiki_entries
    if not all_entries:
        return ""

    def days_label(e: AgingEntry) -> str:
        if e.status == "expired":
            return f"已过期 {-e.days_diff} 天"
        return f"还剩 {e.days_diff} 天"

    lines: list[str] = ["## ⚠ 知识老化预警", "", "以下条目已过期或即将过期，建议在周报中提及或标注：", ""]
    for e in all_entries:
        tag = "EXPIRED" if e.status == "expired" else "AGING  "
        lines.append(f"- [{tag}] `{display_path(e.file)}` — {e.label}（有效期: {e.valid_until}, {days_label(e)}）")
    lines.append("")
    return "\n".join(lines)


def format_aging_log_entry(
    today: dt.date,
    raw_entries: list[AgingEntry],
    wiki_entries: list[AgingEntry],
    report_path: pathlib.Path,
) -> str:
    expired_raw = sum(1 for e in raw_entries if e.status == "expired")
    aging_raw = sum(1 for e in raw_entries if e.status == "aging")
    expired_wiki = sum(1 for e in wiki_entries if e.status == "expired")
    aging_wiki = sum(1 for e in wiki_entries if e.status == "aging")
    return (
        f"\n## {today} 老化扫描\n\n"
        f"- Raw: {expired_raw} 已过期，{aging_raw} 即将过期\n"
        f"- Wiki 判断: {expired_wiki} 已过期，{aging_wiki} 即将过期\n"
        f"- 报告: {display_path(report_path)}\n"
    )


def aging_counts_by_path(
    entries: list[AgingEntry],
) -> dict[pathlib.Path, tuple[int, int]]:
    result: dict[pathlib.Path, tuple[int, int]] = {}
    for e in entries:
        exp, ag = result.get(e.file, (0, 0))
        if e.status == "expired":
            result[e.file] = (exp + 1, ag)
        else:
            result[e.file] = (exp, ag + 1)
    return result


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


def count_judgments(text: str) -> int:
    """Count active (non-deprecated) judgment lines in a wiki file."""
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("**判断**：") or stripped.startswith("**判断**:")):
            continue
        if "~~" in stripped:
            continue
        count += 1
    return count


def extract_wiki_judgments(text: str) -> list[dict]:
    judgments: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("**判断**：") or stripped.startswith("**判断**:"):
            if current:
                judgments.append(current)
            stmt = re.split("[：:]", stripped, maxsplit=1)[-1].strip()
            if "~~" in stmt:
                current = None
                continue
            stmt = re.sub(r"~~(.+?)~~", r"\1", stmt).rstrip("。.")
            current = {"text": stmt, "confidence": "", "valid_until": ""}
            continue
        if current is None:
            continue
        m = re.match(r"[-*]\s*置信度[：:]\s*(.+)", stripped)
        if m:
            current["confidence"] = m.group(1).strip()
            continue
        m = re.match(r"[-*]\s*有效期[：:]\s*(\S+)", stripped)
        if m:
            current["valid_until"] = m.group(1).strip()
    if current:
        judgments.append(current)
    return [j for j in judgments if j["text"]]


def generate_wiki_index(wiki_dir: pathlib.Path, today: dt.datetime) -> dict:
    items: list[dict] = []
    if wiki_dir.exists():
        for path in sorted(wiki_dir.glob("*.md")):
            if path.name == "README.md":
                continue
            text = read_text(path)
            if frontmatter_value(text, "status") != "published":
                continue
            slug = path.stem
            title = slug
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            items.append({
                "slug": slug,
                "title": title,
                "tags": frontmatter_list_value(text, "tags"),
                "sources": frontmatter_list_value(text, "sources"),
                "updated_at": frontmatter_value(text, "updated_at"),
                "judgments": extract_wiki_judgments(text),
            })
    return {"generated_at": today.isoformat(), "items": items}


def list_wiki(wiki_dir: pathlib.Path) -> list[tuple[pathlib.Path, str, int]]:
    """Return list of (path, title, judgment_count) for all wiki topics."""
    rows: list[tuple[pathlib.Path, str, int]] = []
    if not wiki_dir.exists():
        return rows
    for path in sorted(wiki_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        text = read_text(path)
        title = frontmatter_value(text, "title") or path.stem
        # Fallback: first H1 heading
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        n = count_judgments(text)
        rows.append((path, title, n))
    return rows


@dataclasses.dataclass
class DoctorIssue:
    level: str
    code: str
    path: pathlib.Path | None
    message: str


def _frontmatter_block(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    return text[3:end]


def _index_wiki_links(index_text: str) -> set[str]:
    links: set[str] = set()
    for line in index_text.splitlines():
        if line.strip().startswith("<!--"):
            continue
        links.update(re.findall(r"\[\[wiki/([^\]]+)\]\]", line))
    return links


def run_doctor(root: pathlib.Path, raw_dir: pathlib.Path) -> list[DoctorIssue]:
    issues: list[DoctorIssue] = []
    allowed_raw_status = {"fetched", "published"}

    if not raw_dir.exists():
        issues.append(DoctorIssue("ERROR", "raw_dir_missing", raw_dir, "raw_dir 不存在"))
    else:
        for path in sorted(raw_dir.glob("*.md")):
            if path.name == "README.md":
                continue
            text = read_text(path)
            status = frontmatter_value(text, "status")
            if status not in allowed_raw_status:
                issues.append(
                    DoctorIssue(
                        "ERROR",
                        "raw_status",
                        path,
                        f"raw status 应为 fetched/published，当前为 {status or 'missing'}",
                    )
                )

    index_path = root / "index.md"
    index_text = read_text(index_path) if index_path.exists() else ""
    if not index_text:
        issues.append(DoctorIssue("ERROR", "index_missing", index_path, "index.md 不存在或为空"))
    index_links = _index_wiki_links(index_text)
    log_path = root / "log.md"
    log_text = read_text(log_path) if log_path.exists() else ""
    if not log_text:
        issues.append(DoctorIssue("ERROR", "log_missing", log_path, "log.md 不存在或为空"))

    wiki_dir = root / "wiki"
    wiki_files: set[str] = set()
    if not wiki_dir.exists():
        issues.append(DoctorIssue("ERROR", "wiki_dir_missing", wiki_dir, "wiki 目录不存在"))
    else:
        for path in sorted(wiki_dir.glob("*.md")):
            if path.name == "README.md":
                continue
            wiki_files.add(path.name)
            text = read_text(path)
            if not _frontmatter_block(text):
                issues.append(DoctorIssue("ERROR", "wiki_frontmatter", path, "wiki 缺少 frontmatter"))
                continue
            if frontmatter_value(text, "status") != "published":
                issues.append(DoctorIssue("ERROR", "wiki_status", path, "wiki status 应为 published"))
            if frontmatter_value(text, "sources") == "":
                issues.append(DoctorIssue("WARN", "wiki_sources", path, "wiki 缺少 sources 字段"))
            if path.name not in index_links and path.stem not in index_links:
                issues.append(DoctorIssue("ERROR", "wiki_not_indexed", path, "wiki 未登记到 index.md"))
            if log_text and path.name not in log_text:
                issues.append(DoctorIssue("WARN", "wiki_not_logged", path, "wiki 未出现在 log.md 发布记录中"))

    for linked in sorted(index_links):
        linked_name = linked if linked.endswith(".md") else f"{linked}.md"
        if linked_name not in wiki_files:
            issues.append(
                DoctorIssue("ERROR", "index_stale_link", wiki_dir / linked_name, "index.md 指向不存在的 wiki")
            )

    roles_dir = root / "config" / "roles"
    if roles_dir.exists():
        for role_path in sorted(roles_dir.glob("*.yaml")):
            role = _parse_simple_yaml(role_path.read_text(encoding="utf-8"))
            template_rel = str(role.get("output_template", "")).strip()
            if not template_rel:
                issues.append(DoctorIssue("ERROR", "role_template", role_path, "Role Profile 缺少 output_template"))
            elif not (root / template_rel).exists():
                issues.append(DoctorIssue("ERROR", "role_template_missing", root / template_rel, "output_template 文件不存在"))
            instructions_rel = str(role.get("instructions_file", "prompts/weekly.md")).strip()
            if not instructions_rel:
                issues.append(DoctorIssue("ERROR", "role_instructions", role_path, "Role Profile instructions_file 为空"))
            elif not (root / instructions_rel).exists():
                issues.append(DoctorIssue("ERROR", "role_instructions_missing", root / instructions_rel, "instructions_file 文件不存在"))
    else:
        issues.append(DoctorIssue("ERROR", "roles_dir_missing", roles_dir, "config/roles 目录不存在"))

    return issues


def build_doctor_report(issues: list[DoctorIssue]) -> str:
    if not issues:
        return "Doctor OK: raw/wiki/index/role 配置未发现问题。"
    lines = ["Doctor found issues:", ""]
    for issue in issues:
        path = f" `{display_path(issue.path)}`" if issue.path else ""
        lines.append(f"- [{issue.level}] {issue.code}{path}: {issue.message}")
    return "\n".join(lines)


def add_wiki_source(wiki_text: str, raw_filename: str) -> str:
    def _update_sources(m: re.Match) -> str:
        inner = m.group(1).strip()
        items = [v.strip() for v in inner.split(",") if v.strip()] if inner else []
        if raw_filename not in items:
            items.append(raw_filename)
        return f"sources: [{', '.join(items)}]"

    updated, n = re.subn(r"^sources:\s*\[([^\]]*)\]", _update_sources, wiki_text, flags=re.MULTILINE)
    if n:
        return updated

    updated, n = re.subn(r"^sources:.*$", f"sources: [{raw_filename}]", wiki_text, flags=re.MULTILINE)
    if n:
        return updated

    parts = wiki_text.split("---", 2)
    if len(parts) == 3:
        parts[1] = parts[1].rstrip("\n") + f"\nsources: [{raw_filename}]\n"
        return "---".join(parts)

    return f"---\nsources: [{raw_filename}]\n---\n{wiki_text}"


def deprecate_raw(text: str, reason: str, today: dt.date) -> str:
    if re.search(r"^deprecated_reason:", text, re.MULTILINE):
        return re.sub(
            r"^(deprecated_reason:).*$",
            f"deprecated_reason: {reason}",
            text,
            flags=re.MULTILINE,
        )
    parts = text.split("---", 2)
    if len(parts) == 3:
        parts[1] = parts[1].rstrip("\n") + f"\ndeprecated_reason: {reason}\n"
        return "---".join(parts)
    return text


def deprecate_wiki_judgment(
    text: str, judgment_substr: str, reason: str, today: dt.date
) -> str:
    month_str = today.strftime("%Y-%m")
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not (line.startswith("**判断**：") or line.startswith("**判断**:")):
            continue
        stmt = re.split("[：:]", line, maxsplit=1)[-1].strip()
        if "~~" in stmt:
            continue
        if judgment_substr.lower() not in stmt.lower():
            continue
        lines[i] = f"**判断**：~~{stmt}~~（已过时：{month_str}，{reason}）"
        return "\n".join(lines)
    raise ValueError(f"no active judgment matching '{judgment_substr}' found")


def batch_deprecate_raws(
    confirmed: list[tuple["AgingEntry", str]],
    today: dt.date,
) -> int:
    """Apply deprecation to each confirmed raw entry. Returns count of files written."""
    count = 0
    for entry, reason in confirmed:
        text = read_text(entry.file)
        updated = deprecate_raw(text, reason, today)
        entry.file.write_text(updated, encoding="utf-8")
        count += 1
    return count


def batch_deprecate_wiki_judgments(
    confirmed: list[tuple["AgingEntry", str]],
    today: dt.date,
) -> int:
    """Apply deprecation to each confirmed wiki judgment entry. Returns count of files written."""
    count = 0
    for entry, reason in confirmed:
        text = read_text(entry.file)
        updated = deprecate_wiki_judgment(text, entry.label, reason, today)
        entry.file.write_text(updated, encoding="utf-8")
        count += 1
    return count


def _interactive_confirm_loop(
    raw_entries: list["AgingEntry"],
    wiki_entries: list["AgingEntry"],
    today: dt.date,
) -> tuple[int, int]:
    """Interactively prompt user to deprecate expired entries.

    Only prompts for status == 'expired'; aging (not-yet-expired) entries are
    shown in the preceding report but skipped here.
    Returns (raw_deprecated_count, wiki_deprecated_count).
    """
    expired_raw = [e for e in raw_entries if e.status == "expired"]
    expired_wiki = [e for e in wiki_entries if e.status == "expired"]

    if not expired_raw and not expired_wiki:
        print("无已过期条目，无需确认。")
        return 0, 0

    confirmed_raw: list[tuple[AgingEntry, str]] = []
    confirmed_wiki: list[tuple[AgingEntry, str]] = []

    print("\n=== 已过期条目确认 ===")
    print("（输入原因并回车 = 标记 deprecated，直接回车 = 跳过，q = 退出）\n")

    aborted = False
    for e in expired_raw:
        if aborted:
            break
        print(f"[Raw] {display_path(e.file)}")
        print(f"  标题: {e.label}  |  已过期 {-e.days_diff} 天（有效期至 {e.valid_until}）")
        try:
            reason = input("  deprecation 原因: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已中断。")
            aborted = True
            break
        if reason.lower() == "q":
            print("已退出确认流程。")
            aborted = True
            break
        if reason:
            confirmed_raw.append((e, reason))

    for e in expired_wiki:
        if aborted:
            break
        print(f"[Wiki 判断] {display_path(e.file)}")
        print(f"  判断: {e.label}  |  已过期 {-e.days_diff} 天（有效期至 {e.valid_until}）")
        try:
            reason = input("  deprecation 原因: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已中断。")
            break
        if reason.lower() == "q":
            print("已退出确认流程。")
            break
        if reason:
            confirmed_wiki.append((e, reason))

    raw_count = batch_deprecate_raws(confirmed_raw, today)
    wiki_count = batch_deprecate_wiki_judgments(confirmed_wiki, today)

    if raw_count + wiki_count > 0:
        print(f"\n已完成：{raw_count} 条 raw、{wiki_count} 条 wiki 判断标记为 deprecated。")
    else:
        print("\n未标记任何条目。")

    return raw_count, wiki_count


def find_raws_for_topic(
    topic: str,
    raw_dir: pathlib.Path,
) -> list[tuple[pathlib.Path, str, str]]:
    results: list[tuple[pathlib.Path, str, str]] = []
    for path in sorted(raw_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        text = read_text(path)
        targets = frontmatter_list_value(text, "wiki_targets")
        if not any(topic.lower() in t.lower() for t in targets):
            continue
        summary = frontmatter_value(text, "summary")
        key_points_raw = frontmatter_value(text, "key_points")
        results.append((path, summary, key_points_raw))
    return results


def compile_dry_run(
    topic: str,
    raw_dir: pathlib.Path,
    wiki_dir: pathlib.Path,
) -> str:
    """Return a dry-run summary: which raws match, which wiki exists.

    Does not generate any prompt or write any files.
    """
    raw_entries = find_raws_for_topic(topic, raw_dir)
    slug = slugify_topic(topic)
    wiki_path = wiki_dir / f"{slug}.md"

    lines: list[str] = [f"[Dry-run] compile topic: {topic}"]
    lines.append(f"  匹配 raw：{len(raw_entries)} 条")
    for path, _, _ in raw_entries:
        lines.append(f"    - {path.name}")
    if wiki_path.exists():
        lines.append(f"  已有 wiki：{wiki_path.name}（将更新）")
    else:
        # Fuzzy: also check all wiki files for topic in their H1 / filename
        matched_wikis = [
            p for p in sorted(wiki_dir.glob("*.md"))
            if p.name != "README.md" and topic.lower() in p.stem.lower()
        ]
        if matched_wikis:
            lines.append(f"  已有 wiki（模糊匹配）：{', '.join(p.name for p in matched_wikis)}（将更新）")
        else:
            lines.append("  已有 wiki：无（将新建）")
    return "\n".join(lines)


def build_compile_prompt(
    topic: str,
    raw_entries: list[tuple[pathlib.Path, str, str]],
    existing_wiki_path: "pathlib.Path | None",
) -> str:
    existing_wiki_section = ""
    if existing_wiki_path and existing_wiki_path.exists():
        existing_wiki_section = f"""
## 已有 Wiki（请在此基础上更新）

{read_text(existing_wiki_path)}
"""
    else:
        existing_wiki_section = "\n## 已有 Wiki\n\n尚无对应 wiki，请新建。\n"

    raws_section = ""
    for path, summary, key_points in raw_entries:
        raws_section += f"\n### {path.name}\n\n**摘要**：{summary}\n\n**关键点**：{key_points}\n"

    slug = slugify_topic(topic)

    return f"""# Compile Wiki: {topic}

请基于以下 raw 资料，编译或更新主题 wiki《{topic}》。
{existing_wiki_section}
## 参考 Raw 资料（共 {len(raw_entries)} 条）

{raws_section if raws_section else "（无匹配 raw）"}
## 编译指令

- 保留已有 wiki 中仍然有效的判断
- 整合新 raw 带来的新观点、新事实
- 每条判断注明置信度、有效期和来源 raw
- 不确定的内容标注不确定性，不要伪装成事实
- 输出完整的 wiki 文件内容（含 frontmatter）

## 输出目标

请将编译结果写入 `wiki/{slug}.md`（如果文件已存在则更新）。
写入后请将涉及的 raw 文件名加入该 wiki 的 `sources:` frontmatter 字段。
"""


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
    raw_text = read_text(raw_path)
    targets = frontmatter_list_value(raw_text, "wiki_targets")

    weave_back_block = ""
    if targets:
        matched, unmatched = find_matching_wikis(targets, ROOT / "wiki")
        today = dt.date.today()
        wiki_aging = aging_counts_by_path(scan_aging_wikis(ROOT / "wiki", today))
        lines: list[str] = ["", "## 往回织提示（Weave-Back）", ""]
        if matched:
            lines.append("以下已有 wiki 与 wiki_targets 匹配，发布时请检查是否需要更新：")
            lines.append("")
            for target, path, title in matched:
                rel = path.relative_to(ROOT)
                aging_note = ""
                if path in wiki_aging:
                    exp, ag = wiki_aging[path]
                    parts = []
                    if exp:
                        parts.append(f"{exp} 条已过期")
                    if ag:
                        parts.append(f"{ag} 条即将过期")
                    aging_note = f"（⚠ {', '.join(parts)}）"
                lines.append(f"- {rel}（《{title}》）→ 目标：{target}{aging_note}")
        if unmatched:
            lines.append("")
            lines.append("以下 wiki_targets 尚无对应 wiki，建议新建：")
            lines.append("")
            for t in unmatched:
                lines.append(f"- {t}")
        lines.append("")
        lines.append(f"发布后请将 `{raw_path.name}` 加入上述 wiki 的 `sources:` frontmatter 字段。")
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


def build_publish_checklist(raw_path: pathlib.Path, root: pathlib.Path) -> str:
    raw_text = read_text(raw_path)
    status = frontmatter_value(raw_text, "status") or "missing"
    title = frontmatter_value(raw_text, "title") or raw_path.stem
    targets = frontmatter_list_value(raw_text, "wiki_targets")
    matched, unmatched = find_matching_wikis(targets, root / "wiki")

    lines = [
        f"# Publish Checklist: {title}",
        "",
        "## Raw",
        "",
        f"- File: `{display_path(raw_path)}`",
        f"- Status: `{status}`",
        "",
        "## 发布前确认",
        "",
        "- [ ] 用户已明确确认发布",
        "- [ ] raw 的 Auto Summary 和 Suggestions 已填充，不含占位符",
        "- [ ] wiki_targets 已确认",
    ]
    if status == "published":
        lines.append("- [ ] 当前 raw 已是 published，如需重复发布，先确认是增量更新")
    elif status != "fetched":
        lines.append(f"- [ ] 当前 raw status 是 `{status}`，发布前应先修正为 `fetched` 或确认生命周期语义")

    lines.extend(["", "## Wiki 目标", ""])
    if matched:
        lines.append("应优先更新已有 wiki：")
        lines.append("")
        for target, path, wiki_title in matched:
            lines.append(f"- [ ] `{display_path(path)}`（《{wiki_title}》）← `{target}`")
    if unmatched:
        if matched:
            lines.append("")
        lines.append("尚无匹配 wiki，发布时建议新建：")
        lines.append("")
        for target in unmatched:
            slug = slugify_topic(target)
            lines.append(f"- [ ] `wiki/{slug}.md` ← `{target}`")
    if not targets:
        lines.append("- [ ] raw 未设置 wiki_targets，先判断更新现有 wiki 还是新建主题")

    lines.extend(
        [
            "",
            "## 发布时必须更新",
            "",
            "- [ ] `wiki/*.md`：新增或更新主题笔记，避免按来源建笔记",
            "- [ ] wiki frontmatter：`status: published`，并把 raw 文件名写入 `sources:`",
            "- [ ] `index.md`：新增或更新 wiki 入口摘要",
            "- [ ] `log.md`：记录发布日期、wiki 文件和本次沉淀内容",
            "- [ ] raw frontmatter：`status: published`",
            "",
            "## 发布后验证",
            "",
            "- [ ] `python3 scripts/kb.py doctor` 无 ERROR",
        ]
    )
    return "\n".join(lines)


def load_role_profile(role_id: str) -> dict:
    config_path = ROOT / "config" / "roles" / f"{role_id}.yaml"
    if not config_path.exists():
        raise SystemExit(f"role profile not found: {config_path}")
    return _parse_simple_yaml(config_path.read_text(encoding="utf-8"))


def _render_template(template: str, ctx: dict) -> str:
    """Replace %%MARKER%% placeholders in template with values from ctx."""
    for key, value in ctx.items():
        template = template.replace(f"%%{key}%%", value)
    return template


def _build_weekly_prompt_from_root(
    root: pathlib.Path,
    raw_dir: pathlib.Path,
    role_id: str = "technical_practitioner",
) -> str:
    profile_path = root / "profile.md"
    prompts_dir = root / "prompts"
    wiki_dir = root / "wiki"

    config_path = root / "config" / "roles" / f"{role_id}.yaml"
    if not config_path.exists():
        raise SystemExit(f"role profile not found: {config_path}")
    profile = _parse_simple_yaml(config_path.read_text(encoding="utf-8"))

    time_window = int(profile.get("time_window_days", 7))
    threshold = int(profile.get("cold_start_threshold", 5))
    focus_areas = profile.get("focus_areas", [])
    if isinstance(focus_areas, str):
        focus_areas = [focus_areas]
    template_rel = profile.get("output_template", "")

    today = dt.date.today()
    cutoff = today - dt.timedelta(days=time_window)
    week_label = today.strftime("%Y-W%W")

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
    if not raws_section:
        raws_section = "（本周无 raw 资料）"

    wiki_section = ""
    if wiki_dir.exists():
        for path in sorted(wiki_dir.glob("*.md")):
            if path.name == "README.md":
                continue
            wiki_section += f"\n---\n### wiki/{path.name}\n\n{read_text(path)}\n"
    if not wiki_section:
        wiki_section = "（暂无 wiki 内容）"

    weekly_instructions = ""
    instructions_rel = str(profile.get("instructions_file", "prompts/weekly.md")).strip() or "prompts/weekly.md"
    instructions_path = root / instructions_rel
    if instructions_path.exists():
        weekly_instructions = read_text(instructions_path)

    aging_raw_entries = scan_aging_raws(raw_dir, today)
    aging_wiki_entries = scan_aging_wikis(wiki_dir, today)
    aging_block = build_aging_block(aging_raw_entries, aging_wiki_entries)
    aging_section = f"\n{aging_block}" if aging_block else ""

    focus_str = "、".join(focus_areas) if focus_areas else "技术领域"
    profile_text = read_text(profile_path) if profile_path.exists() else ""

    ctx = {
        "WEEK_LABEL": week_label,
        "COLD_START_WARNING": cold_start_warning,
        "AGING_SECTION": aging_section,
        "PROFILE": profile_text,
        "FOCUS_AREAS": focus_str,
        "WEEKLY_INSTRUCTIONS": weekly_instructions,
        "RAWS_HEADER": f"{cutoff} 至 {today}，共 {len(raws)} 条",
        "RAWS_SECTION": raws_section,
        "WIKI_SECTION": wiki_section,
        "CUTOFF_DATE": str(cutoff),
        "TODAY": str(today),
        "RAW_COUNT": str(len(raws)),
    }

    # 尝试加载模板
    if template_rel:
        template_path = root / template_rel
        if template_path.exists():
            return _render_template(read_text(template_path), ctx)

    # Fallback：原有硬编码格式
    return f"""# 生成 {week_label} 技术者周报

{cold_start_warning}{aging_section}
## 用户 Profile

{profile_text}

## 角色关注领域

{focus_str}

## 周报生成指令

{weekly_instructions}

## 本周 Raw 资料（{cutoff} 至 {today}，共 {len(raws)} 条）

{raws_section}

## Wiki 长期知识上下文

{wiki_section}

## 输出目标

请生成 `reviews/{week_label}.md` 的内容。直接输出 Markdown 正文，不需要额外说明。
"""


def weekly_cache_path(root: pathlib.Path, role_id: str, week_label: str) -> pathlib.Path:
    """Return the cache file path for a given role and week."""
    return root / ".weekly-cache" / f"{role_id}-{week_label}.txt"


def build_weekly_prompt(role_id: str = "technical_practitioner", use_cache: bool = True) -> str:
    root = ROOT
    raw_dir = _require_raw_dir()
    week_label = dt.date.today().strftime("%Y-W%W")
    cache_file = weekly_cache_path(root, role_id, week_label)

    if use_cache and cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    prompt = _build_weekly_prompt_from_root(root=root, raw_dir=raw_dir, role_id=role_id)

    cache_file.parent.mkdir(exist_ok=True)
    cache_file.write_text(prompt, encoding="utf-8")
    return prompt


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

    list_cmd = sub.add_parser("list", help="list raw notes or wiki topics")
    list_cmd.add_argument("--status", help="filter by raw status, for example fetched")
    list_cmd.add_argument(
        "--aging",
        action="store_true",
        help="include aging status column (active/aging/expired/-)",
    )
    list_cmd.add_argument(
        "--wiki",
        action="store_true",
        help="list wiki topics with judgment counts instead of raw notes",
    )

    review = sub.add_parser("review", help="print a review prompt for a raw note")
    review.add_argument("raw_file", nargs="?", help="raw note path; defaults to latest raw")

    publish = sub.add_parser("publish-prompt", help="print a publish prompt for a raw note")
    publish.add_argument("raw_file", nargs="?", help="raw note path; defaults to latest raw")

    publish_checklist = sub.add_parser("publish-checklist", help="print a publish checklist for a raw note")
    publish_checklist.add_argument("raw_file", nargs="?", help="raw note path; defaults to latest raw")

    weekly = sub.add_parser("weekly", help="generate weekly report prompt")
    weekly.add_argument("--role", default="technical_practitioner", help="role profile id")
    weekly.add_argument("--output", action="store_true", help="save prompt to reviews/YYYY-WW-prompt.md")
    weekly.add_argument(
        "--no-cache",
        action="store_true",
        dest="no_cache",
        help="ignore cached prompt and regenerate from raw/wiki",
    )

    deprecate_cmd = sub.add_parser("deprecate", help="mark a raw or wiki judgment as deprecated")
    deprecate_cmd.add_argument("file", help="path to raw or wiki file (relative to repo root or absolute)")
    deprecate_cmd.add_argument("--reason", default="", help="deprecation reason text")
    deprecate_cmd.add_argument("--judgment", default="", help="substring of wiki judgment statement to deprecate")

    compile_cmd = sub.add_parser("compile", help="compile a wiki topic from matching raws")
    compile_cmd.add_argument("topic", help="wiki topic name (used to match wiki_targets in raws)")
    compile_cmd.add_argument("--wiki", default="", help="path to existing wiki file to update (optional)")
    compile_cmd.add_argument(
        "--output",
        action="store_true",
        help="save prompt to reviews/<topic>-compile-YYYY-MM-DD.md",
    )
    compile_cmd.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="preview matching raws and wiki without generating a prompt",
    )

    aging_cmd = sub.add_parser("aging", help="scan for expired or soon-to-expire entries")
    aging_cmd.add_argument(
        "--threshold",
        type=int,
        default=30,
        help="days before expiry to flag as aging (default: 30)",
    )
    aging_cmd.add_argument(
        "--output",
        action="store_true",
        help="save report to reviews/aging-YYYY-MM-DD.md",
    )
    aging_cmd.add_argument(
        "--confirm",
        action="store_true",
        help="interactively confirm and mark expired entries as deprecated",
    )

    sub.add_parser("doctor", help="check raw/wiki/index/log/role configuration consistency")

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
        if args.wiki:
            wiki_dir = ROOT / "wiki"
            wiki_rows = list_wiki(wiki_dir)
            for path, title, n in wiki_rows:
                print(f"{n} 条判断\t{display_path(path)}\t{title}")
            return 0
        rows = list_raw(args.status)
        if not rows:
            return 0
        today = dt.date.today()
        for path, raw_status, title in rows:
            if args.aging:
                text = read_text(path)
                aging = raw_aging_status(text, today)
                print(f"{raw_status}\t{aging}\t{display_path(path)}\t{title}")
            else:
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

    if args.command == "publish-checklist":
        raw_path = resolve_raw(args.raw_file)
        print(build_publish_checklist(raw_path, ROOT))
        return 0

    if args.command == "weekly":
        prompt = build_weekly_prompt(args.role, use_cache=not args.no_cache)
        print(prompt)
        if args.output:
            week_label = dt.date.today().strftime("%Y-W%W")
            out_path = ROOT / "reviews" / f"{week_label}-prompt.md"
            out_path.write_text(prompt, encoding="utf-8")
            print(f"\n保存至 {display_path(out_path)}", file=sys.stderr)
        return 0

    if args.command == "deprecate":
        path = pathlib.Path(args.file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise SystemExit(f"file not found: {args.file}")
        text = read_text(path)
        today = dt.date.today()
        if args.judgment:
            try:
                updated = deprecate_wiki_judgment(text, args.judgment, args.reason, today)
            except ValueError as e:
                raise SystemExit(str(e))
        else:
            updated = deprecate_raw(text, args.reason, today)
        path.write_text(updated, encoding="utf-8")
        print(f"已标记为 deprecated：{display_path(path)}")
        return 0

    if args.command == "compile":
        raw_dir = _require_raw_dir()
        if args.dry_run:
            wiki_dir = ROOT / "wiki"
            print(compile_dry_run(args.topic, raw_dir, wiki_dir))
            return 0
        raw_entries = find_raws_for_topic(args.topic, raw_dir)
        existing_wiki_path = None
        if args.wiki:
            p = pathlib.Path(args.wiki)
            existing_wiki_path = p if p.is_absolute() else ROOT / p
        prompt = build_compile_prompt(args.topic, raw_entries, existing_wiki_path)
        print(prompt)
        if args.output:
            today = dt.date.today()
            slug = slugify_topic(args.topic)
            out_path = ROOT / "reviews" / f"{slug}-compile-{today}.md"
            out_path.write_text(prompt, encoding="utf-8")
            print(f"\n保存至 {display_path(out_path)}", file=sys.stderr)
        return 0

    if args.command == "aging":
        today = dt.date.today()
        raw_dir = _require_raw_dir()
        wiki_dir = ROOT / "wiki"
        raw_entries = scan_aging_raws(raw_dir, today, args.threshold)
        wiki_entries = scan_aging_wikis(wiki_dir, today, args.threshold)
        report = build_aging_report(raw_entries, wiki_entries, today)
        print(report)
        if args.output:
            out_path = ROOT / "reviews" / f"aging-{today}.md"
            out_path.write_text(report, encoding="utf-8")
            print(f"\n保存至 {display_path(out_path)}", file=sys.stderr)
            log_path = ROOT / "log.md"
            if log_path.exists():
                entry = format_aging_log_entry(today, raw_entries, wiki_entries, out_path)
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(entry)
        if args.confirm:
            _interactive_confirm_loop(raw_entries, wiki_entries, today)
        return 0

    if args.command == "doctor":
        issues = run_doctor(ROOT, _require_raw_dir())
        print(build_doctor_report(issues))
        return 1 if any(issue.level == "ERROR" for issue in issues) else 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
