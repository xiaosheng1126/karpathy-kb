#!/usr/bin/env python3
"""
Token-aware source reader for the Karpathy-style knowledge base.

The reader has one job: turn a source into a compact, traceable text payload.
It deliberately prefers cheap, source-specific reads over crawling everything.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import html.parser
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_MAX_CHARS = 24000
READ_DEPTH_BUDGETS = {
    "preview": 6000,
    "standard": DEFAULT_MAX_CHARS,
    "full": 80000,
}
USER_AGENT = "Mozilla/5.0 kb-source-reader/0.1"
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent


@dataclasses.dataclass
class ReaderOutput:
    input_type: str
    source_type: str
    title: str
    url: str = ""
    local_path: str = ""
    author: str = ""
    published_at: str = ""
    fetched_at: str = dataclasses.field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    reader: str = "scripts/source_reader.py"
    read_quality: str = "basic"
    strategy: str = ""
    token_policy: str = ""
    read_depth: str = "standard"
    content: str = ""
    preview: dict[str, object] = dataclasses.field(default_factory=dict)
    next_actions: list[dict[str, str]] = dataclasses.field(default_factory=list)
    metadata: dict[str, object] = dataclasses.field(default_factory=dict)
    assets: list[str] = dataclasses.field(default_factory=list)
    errors: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


class TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self._in_title = False
        self.title = ""
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"script", "style", "noscript", "svg", "canvas"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in {"article", "section", "main", "p", "li", "br", "h1", "h2", "h3", "h4", "pre", "tr"}:
            self.parts.append("\n")
        if tag == "meta":
            name = attrs_dict.get("name") or attrs_dict.get("property") or ""
            content = attrs_dict.get("content") or ""
            if name in {"og:title", "twitter:title"} and content and not self.title:
                self.title = content

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = normalize_space(data)
        if not text:
            return
        if self._in_title:
            self.title += text
        if not self._skip:
            self.parts.append(text)

    def text(self) -> str:
        return normalize_text("\n".join(self.parts))


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def cap_text(text: str, max_chars: int) -> tuple[str, bool]:
    text = normalize_text(text)
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    head_chars = max(1, int(max_chars * 0.72))
    tail_chars = max(1, max_chars - head_chars)
    clipped = (
        text[:head_chars].rstrip()
        + "\n\n[... content clipped by source-reader to save tokens ...]\n\n"
        + text[-tail_chars:].lstrip()
    )
    return clipped, True


def estimate_tokens(text: str) -> int:
    # Mixed Chinese/English docs vary a lot; this is a conservative UI hint, not billing data.
    return max(1, int(len(text) / 2.2))


def extract_headings(text: str, limit: int = 12) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        stripped = normalize_space(line)
        if not stripped:
            continue
        if re.match(r"^#{1,4}\s+\S", stripped):
            headings.append(re.sub(r"^#{1,4}\s+", "", stripped))
        elif re.match(r"^(\d+(\.\d+)*[.、)]\s*|[一二三四五六七八九十]+[、.]\s*)\S", stripped):
            headings.append(stripped)
        if len(headings) >= limit:
            break
    return headings


def extract_lead_points(text: str, limit: int = 5) -> list[str]:
    points: list[str] = []
    for part in re.split(r"\n{2,}", text):
        item = normalize_space(part)
        if len(item) < 20:
            continue
        points.append(item[:220] + ("..." if len(item) > 220 else ""))
        if len(points) >= limit:
            break
    return points


def build_preview(result: ReaderOutput) -> dict[str, object]:
    content = result.content or ""
    content_chars = len(content)
    body_length = result.metadata.get("body_length")
    if isinstance(body_length, int) and body_length > content_chars:
        content_chars = body_length
    return {
        "title": result.title,
        "source_type": result.source_type,
        "read_quality": result.read_quality,
        "strategy": result.strategy,
        "content_chars": content_chars,
        "estimated_tokens": estimate_tokens(content),
        "headings": extract_headings(content),
        "lead_points": extract_lead_points(content),
        "is_truncated": "clipped" in result.token_policy,
    }


def build_command(
    source: str,
    read_depth: str,
    fmt: str,
    mode: str,
    browser_profile: str,
    headless: bool,
    interactive_login: bool,
    login_timeout_ms: int,
) -> str:
    parts = [
        "python3",
        "scripts/source_reader.py",
        shell_quote(source),
        "--read-depth",
        read_depth,
        "--format",
        fmt,
        "--mode",
        mode,
    ]
    if browser_profile:
        parts.extend(["--browser-profile", shell_quote(browser_profile)])
    if headless:
        parts.append("--headless")
    if interactive_login:
        parts.extend(["--interactive-login", "--login-timeout-ms", str(login_timeout_ms)])
    return " ".join(parts)


def shell_quote(value: str) -> str:
    if re.match(r"^[A-Za-z0-9_./:@%+=,-]+$", value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def build_next_actions(
    result: ReaderOutput,
    source: str,
    mode: str,
    browser_profile: str,
    headless: bool,
    interactive_login: bool,
    login_timeout_ms: int,
) -> list[dict[str, str]]:
    actions = [
        {
            "id": "deep_read",
            "label": "深读全文",
            "description": "提高读取预算，适合你决定继续分析这份资料。",
            "command": build_command(source, "full", "md", mode, browser_profile, headless, interactive_login, login_timeout_ms),
        },
        {
            "id": "summarize_structure",
            "label": "结构化总结",
            "description": "让 LLM 基于当前内容输出背景、核心观点、风险和建议。",
            "prompt": "请基于上面的 Source Reader 输出做结构化总结，并指出是否值得继续沉淀。",
        },
        {
            "id": "deposit_raw",
            "label": "沉淀为 raw",
            "description": "创建 Obsidian raw，保留原始内容，并把总结和建议留给确认流程。",
            "command": build_kb_raw_command(source, mode, browser_profile, headless, interactive_login, login_timeout_ms),
        },
        {
            "id": "ask_followup",
            "label": "追问细节",
            "description": "针对某个章节、实现、风险或决策点继续提问。",
            "prompt": "我想继续追问这份资料中的一个具体问题：",
        },
    ]
    if any("Playwright is not installed" in error for error in result.errors):
        actions.insert(
            0,
            {
                "id": "install_playwright",
                "label": "安装浏览器读取依赖",
                "description": "安装 Playwright 和 Chromium，之后可读取 JS 渲染或登录态页面。",
                "command": "python3 scripts/install.py --target both --install-playwright",
            },
        )
    if result.read_quality in {"blocked", "failed"}:
        actions.insert(
            0,
            {
                "id": "retry_with_login",
                "label": "登录后重试",
                "description": "打开持久化浏览器 profile，手动登录或授权后继续读取。",
                "command": build_command(
                    source,
                    "preview",
                    "md",
                    "browser",
                    browser_profile or ".source-reader/profiles/default",
                    False,
                    True,
                    login_timeout_ms,
                ),
            },
        )
    return actions


def build_kb_raw_command(
    source: str,
    mode: str,
    browser_profile: str,
    headless: bool,
    interactive_login: bool,
    login_timeout_ms: int,
) -> str:
    parts = [
        "python3",
        "scripts/kb.py",
        "raw",
        shell_quote(source),
        "--mode",
        mode,
    ]
    if browser_profile:
        parts.extend(["--browser-profile", shell_quote(browser_profile)])
    if headless:
        parts.append("--headless")
    if interactive_login:
        parts.extend(["--interactive-login", "--login-timeout-ms", str(login_timeout_ms)])
    return " ".join(parts)


def attach_interaction(
    result: ReaderOutput,
    source: str,
    read_depth: str,
    mode: str,
    browser_profile: str,
    headless: bool,
    interactive_login: bool,
    login_timeout_ms: int,
) -> ReaderOutput:
    result.read_depth = read_depth
    result.preview = build_preview(result)
    result.next_actions = build_next_actions(
        result,
        source,
        mode,
        browser_profile,
        headless,
        interactive_login,
        login_timeout_ms,
    )
    result.metadata["read_depth"] = read_depth
    return result


def command_exists(command: str) -> bool:
    proc = subprocess.run(["/usr/bin/env", "which", command], text=True, capture_output=True, check=False)
    return proc.returncode == 0


def run_check(command: list[str], cwd: pathlib.Path | None = None) -> tuple[bool, str]:
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (proc.stdout.strip() or proc.stderr.strip())
    return proc.returncode == 0, output


def source_reader_doctor(browser_profile: str = ".source-reader/profiles/default") -> dict[str, object]:
    profile_path = pathlib.Path(browser_profile).expanduser()
    if not profile_path.is_absolute():
        profile_path = (ROOT_DIR / profile_path).resolve()

    node_ok = command_exists("node")
    npm_ok = command_exists("npm")
    package_json = ROOT_DIR / "package.json"
    browser_reader = SCRIPT_DIR / "browser_reader.mjs"
    playwright_ok = False
    playwright_message = ""
    if node_ok:
        playwright_ok, playwright_message = run_check(
            ["node", "-e", "import('playwright').then(()=>console.log('ok')).catch(e=>{console.error(e.message);process.exit(1)})"],
            cwd=ROOT_DIR,
        )

    checks = {
        "root": str(ROOT_DIR),
        "node": node_ok,
        "npm": npm_ok,
        "package_json": package_json.exists(),
        "browser_reader": browser_reader.exists(),
        "playwright": playwright_ok,
        "browser_profile": profile_path.exists(),
        "browser_profile_path": str(profile_path),
    }
    recommendations: list[str] = []
    if not node_ok:
        recommendations.append("Install Node.js before using browser mode.")
    if not npm_ok:
        recommendations.append("Install npm before using browser mode.")
    if not playwright_ok:
        recommendations.append("Run: python3 scripts/install.py --target both --install-playwright")
    if not profile_path.exists():
        recommendations.append(f"Create browser profile directory: {profile_path}")

    return {
        "status": "ok" if all([node_ok, npm_ok, package_json.exists(), browser_reader.exists(), playwright_ok]) else "needs_setup",
        "checks": checks,
        "playwright_message": playwright_message,
        "recommendations": recommendations,
    }


def request_url(url: str) -> tuple[bytes, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            final_url = response.geturl()
            content_type = response.headers.get("content-type", "")
            return response.read(), content_type, final_url
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc)) from exc


def decode_body(body: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([\w.-]+)", content_type, re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    return body.decode(charset, errors="replace")


def extract_html(html: str) -> tuple[str, str]:
    extractor = TextExtractor()
    extractor.feed(html)
    return extractor.title.strip(), extractor.text()


def looks_like_auth_wall(requested_url: str, final_url: str, title: str, content: str) -> bool:
    parsed_final = urllib.parse.urlparse(final_url)
    parsed_requested = urllib.parse.urlparse(requested_url)
    final_path = parsed_final.path.lower()
    final_query = urllib.parse.parse_qs(parsed_final.query)
    joined = f"{title}\n{content}".lower()
    login_words = ("login", "signin", "sign in", "登录", "登陆", "授权", "认证")

    if any(word in final_path for word in ("/login", "/signin", "/passport")):
        return True
    if any(key in final_query for key in ("goto", "redirect", "redirect_uri", "return_url", "next")):
        if any(word in joined for word in login_words):
            return True
    if parsed_final.netloc == parsed_requested.netloc and len(content) < 300:
        return any(word in joined for word in login_words)
    return False


def looks_like_js_shell(decoded: str, content: str) -> bool:
    lowered = decoded.lower()
    script_count = lowered.count("<script")
    app_markers = (
        'id="app"',
        "id='app'",
        'id="root"',
        "id='root'",
        "__next_data__",
        "window.__initial_state__",
        "webpack",
        "vite",
    )
    if len(content) >= 1200:
        return False
    if any(marker in lowered for marker in app_markers) and script_count >= 2:
        return True
    if script_count >= 8 and len(content) < 500:
        return True
    return False


def read_basic_url(url: str, max_chars: int) -> ReaderOutput:
    body, content_type, final_url = request_url(url)
    decoded = decode_body(body, content_type)
    is_html = "html" in content_type or decoded.lstrip().startswith("<")
    if is_html:
        title, content = extract_html(decoded)
        strategy = "html_text_extraction"
    else:
        title, content = final_url, decoded
        strategy = "plain_text_response"
    content, clipped = cap_text(content, max_chars)
    auth_wall = looks_like_auth_wall(url, final_url, title, content)
    js_shell = is_html and looks_like_js_shell(decoded, content)
    metadata: dict[str, object] = {
        "content_type": content_type,
        "requested_url": url,
    }
    errors: list[str] = []
    read_quality = "basic" if content else "partial"
    if auth_wall:
        read_quality = "blocked"
        metadata["blocked_by"] = "auth_wall"
        errors.append("Page appears to require login or authorization. Retry with browser/auth reader.")
    elif js_shell:
        read_quality = "partial"
        metadata["maybe_js_rendered"] = True
        errors.append("Page looks like a JavaScript-rendered shell. Retry with browser reader.")
    return ReaderOutput(
        input_type="url",
        source_type="webpage",
        title=title or final_url,
        url=final_url,
        read_quality=read_quality,
        strategy=strategy,
        token_policy=token_policy(max_chars, clipped),
        content=content or "读取结果为空。",
        metadata=metadata,
        errors=errors,
    )


def read_browser_url(
    url: str,
    max_chars: int,
    browser_profile: str,
    headless: bool = False,
    interactive_login: bool = False,
    login_timeout_ms: int = 180000,
) -> ReaderOutput:
    script = SCRIPT_DIR / "browser_reader.mjs"
    command = [
        "node",
        str(script),
        "--url",
        url,
        "--profile",
        browser_profile,
        "--max-chars",
        str(max_chars),
    ]
    if headless:
        command.append("--headless")
    if interactive_login:
        command.extend(["--interactive-login", "--login-timeout-ms", str(login_timeout_ms)])
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or f"browser reader exited with {proc.returncode}"
        try:
            parsed_error = json.loads(message)
            message = str(parsed_error.get("error") or message)
        except json.JSONDecodeError:
            pass
        return ReaderOutput(
            input_type="url",
            source_type="webpage",
            title=url,
            url=url,
            read_quality="failed",
            strategy="playwright_persistent_profile",
            token_policy=token_policy(max_chars, False),
            content="",
            metadata={"browser_profile": str(pathlib.Path(browser_profile).expanduser())},
            errors=[message],
        )

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return ReaderOutput(
            input_type="url",
            source_type="webpage",
            title=url,
            url=url,
            read_quality="failed",
            strategy="playwright_persistent_profile",
            token_policy=token_policy(max_chars, False),
            content="",
            metadata={"browser_profile": str(pathlib.Path(browser_profile).expanduser())},
            errors=[f"browser reader returned non-json output: {exc}"],
        )

    return ReaderOutput(
        input_type="url",
        source_type="webpage",
        title=str(payload.get("title") or url),
        url=str(payload.get("url") or url),
        read_quality=str(payload.get("read_quality") or "browser"),
        strategy=str(payload.get("strategy") or "playwright_persistent_profile"),
        token_policy=str(payload.get("token_policy") or token_policy(max_chars, False)),
        content=str(payload.get("content") or ""),
        metadata=dict(payload.get("metadata") or {}),
        errors=list(payload.get("errors") or []),
    )


def raw_github_url(owner: str, repo: str, branch: str, path: str) -> str:
    quoted_path = "/".join(urllib.parse.quote(part) for part in path.split("/"))
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{quoted_path}"


def github_api(url: str) -> object:
    body, content_type, _ = request_url(url)
    if "json" not in content_type:
        raise RuntimeError(f"GitHub API returned non-json content type: {content_type}")
    return json.loads(decode_body(body, content_type))


def read_github_repo_readme(owner: str, repo: str, original_url: str, max_chars: int) -> ReaderOutput:
    errors: list[str] = []
    candidates = [
        ("main", "README.md"),
        ("master", "README.md"),
        ("main", "readme.md"),
        ("master", "readme.md"),
        ("main", "README"),
        ("master", "README"),
    ]
    for branch, path in candidates:
        readme_url = raw_github_url(owner, repo, branch, path)
        try:
            body, content_type, final_url = request_url(readme_url)
        except RuntimeError as exc:
            errors.append(f"{branch}/{path}: {exc}")
            continue
        content = decode_body(body, content_type)
        content, clipped = cap_text(content, max_chars)
        return ReaderOutput(
            input_type="url",
            source_type="github_repo",
            title=f"{owner}/{repo} README",
            url=original_url,
            read_quality="targeted",
            strategy="github_repo_readme_only",
            token_policy=token_policy(max_chars, clipped),
            content=content,
            metadata={"owner": owner, "repo": repo, "read_url": final_url, "branch": branch, "path": path},
            errors=errors,
        )
    return ReaderOutput(
        input_type="url",
        source_type="github_repo",
        title=f"{owner}/{repo}",
        url=original_url,
        read_quality="failed",
        strategy="github_repo_readme_only",
        token_policy=token_policy(max_chars, False),
        content="",
        metadata={"owner": owner, "repo": repo},
        errors=errors or ["README not found"],
    )


def read_github_blob(owner: str, repo: str, parts: list[str], original_url: str, max_chars: int) -> ReaderOutput:
    branch = parts[2]
    path = "/".join(parts[3:])
    url = raw_github_url(owner, repo, branch, path)
    body, content_type, final_url = request_url(url)
    content, clipped = cap_text(decode_body(body, content_type), max_chars)
    return ReaderOutput(
        input_type="url",
        source_type="github_file",
        title=f"{owner}/{repo}/{path}",
        url=original_url,
        read_quality="targeted",
        strategy="github_blob_raw_file_only",
        token_policy=token_policy(max_chars, clipped),
        content=content,
        metadata={"owner": owner, "repo": repo, "branch": branch, "path": path, "read_url": final_url},
    )


def read_github_issue(owner: str, repo: str, issue_number: str, original_url: str, max_chars: int) -> ReaderOutput:
    issue = github_api(f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}")
    comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments?per_page=12"
    comments: list[dict[str, object]] = []
    errors: list[str] = []
    try:
        comments_data = github_api(comments_url)
        if isinstance(comments_data, list):
            comments = comments_data[:12]
    except RuntimeError as exc:
        errors.append(f"comments: {exc}")

    lines = [
        f"# {issue.get('title', '')}",
        "",
        f"State: {issue.get('state', '')}",
        f"Author: {(issue.get('user') or {}).get('login', '') if isinstance(issue.get('user'), dict) else ''}",
        "",
        normalize_text(str(issue.get("body") or "")),
    ]
    if comments:
        lines.append("\n## First comments")
    for item in comments:
        user = item.get("user") if isinstance(item, dict) else {}
        login = user.get("login", "") if isinstance(user, dict) else ""
        lines.append(f"\n### {login} at {item.get('created_at', '')}")
        lines.append(normalize_text(str(item.get("body") or "")))

    content, clipped = cap_text("\n".join(lines), max_chars)
    return ReaderOutput(
        input_type="url",
        source_type="github_issue_or_pr",
        title=str(issue.get("title") or f"{owner}/{repo}#{issue_number}"),
        url=original_url,
        author=(issue.get("user") or {}).get("login", "") if isinstance(issue.get("user"), dict) else "",
        published_at=str(issue.get("created_at") or ""),
        read_quality="targeted",
        strategy="github_issue_body_plus_first_12_comments",
        token_policy=token_policy(max_chars, clipped),
        content=content,
        metadata={"owner": owner, "repo": repo, "number": issue_number, "comments_read": len(comments)},
        errors=errors,
    )


def read_github_release(owner: str, repo: str, parts: list[str], original_url: str, max_chars: int) -> ReaderOutput:
    if len(parts) >= 4 and parts[2] == "tag":
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{urllib.parse.quote(parts[3])}"
    else:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    release = github_api(api_url)
    body = normalize_text(str(release.get("body") or ""))
    content, clipped = cap_text(f"# {release.get('name') or release.get('tag_name')}\n\n{body}", max_chars)
    return ReaderOutput(
        input_type="url",
        source_type="github_release",
        title=str(release.get("name") or release.get("tag_name") or f"{owner}/{repo} release"),
        url=original_url,
        author=(release.get("author") or {}).get("login", "") if isinstance(release.get("author"), dict) else "",
        published_at=str(release.get("published_at") or ""),
        read_quality="targeted",
        strategy="github_release_notes_only",
        token_policy=token_policy(max_chars, clipped),
        content=content,
        metadata={"owner": owner, "repo": repo, "tag": release.get("tag_name", "")},
    )


def read_gist(parts: list[str], original_url: str, max_chars: int) -> ReaderOutput:
    if len(parts) < 2:
        return read_basic_url(original_url, max_chars)
    gist_id = parts[1]
    api = github_api(f"https://api.github.com/gists/{gist_id}")
    files = api.get("files", {}) if isinstance(api, dict) else {}
    selected_name = ""
    selected = ""
    if isinstance(files, dict):
        preferred = sorted(files.values(), key=lambda item: 0 if str(item.get("filename", "")).lower().endswith((".md", ".txt")) else 1)
        if preferred:
            item = preferred[0]
            selected_name = str(item.get("filename") or "")
            selected = str(item.get("content") or "")
    selected, clipped = cap_text(selected, max_chars)
    return ReaderOutput(
        input_type="url",
        source_type="github_gist",
        title=str(api.get("description") or selected_name or gist_id) if isinstance(api, dict) else gist_id,
        url=original_url,
        author=(api.get("owner") or {}).get("login", "") if isinstance(api, dict) and isinstance(api.get("owner"), dict) else "",
        published_at=str(api.get("created_at") or "") if isinstance(api, dict) else "",
        read_quality="targeted" if selected else "partial",
        strategy="gist_first_markdown_or_text_file_only",
        token_policy=token_policy(max_chars, clipped),
        content=selected,
        metadata={"gist_id": gist_id, "selected_file": selected_name, "file_count": len(files) if isinstance(files, dict) else 0},
    )


def read_github(url: str, max_chars: int) -> ReaderOutput:
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.netloc == "gist.github.com":
        return read_gist(parts, url, max_chars)
    if len(parts) < 2:
        return read_basic_url(url, max_chars)
    owner, repo = parts[0], parts[1]
    rest = parts[2:]
    if not rest:
        return read_github_repo_readme(owner, repo, url, max_chars)
    if rest[0] == "blob" and len(rest) >= 3:
        return read_github_blob(owner, repo, rest, url, max_chars)
    if rest[0] in {"issues", "pull"} and len(rest) >= 2:
        return read_github_issue(owner, repo, rest[1], url, max_chars)
    if rest[0] == "releases":
        return read_github_release(owner, repo, rest, url, max_chars)
    if rest[0] == "tree":
        result = read_github_repo_readme(owner, repo, url, max_chars)
        result.strategy = "github_tree_fallback_repo_readme_only"
        result.metadata["requested_path"] = "/".join(rest)
        return result
    return read_github_repo_readme(owner, repo, url, max_chars)


def command_exists(command: str) -> bool:
    try:
        subprocess.run([command, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def read_video(url: str, max_chars: int) -> ReaderOutput:
    if not command_exists("yt-dlp"):
        return ReaderOutput(
            input_type="url",
            source_type="video",
            title=url,
            url=url,
            read_quality="partial",
            strategy="video_metadata_stub_no_yt_dlp",
            token_policy=token_policy(max_chars, False),
            content="未安装 yt-dlp，无法自动读取字幕。建议安装后优先读取字幕/章节，而不是下载视频或抓取评论。",
            errors=["yt-dlp not found"],
        )

    with tempfile.TemporaryDirectory() as tmp:
        output_tpl = str(pathlib.Path(tmp) / "subtitle.%(ext)s")
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-subs",
            "--write-subs",
            "--sub-langs",
            "zh-CN,zh-Hans,zh,en.*",
            "--sub-format",
            "vtt",
            "--output",
            output_tpl,
            "--print",
            "title",
            url,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
        title = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else url
        subtitle_files = sorted(pathlib.Path(tmp).glob("*.vtt"))
        if not subtitle_files:
            return ReaderOutput(
                input_type="url",
                source_type="video",
                title=title,
                url=url,
                read_quality="partial",
                strategy="video_subtitle_attempt",
                token_policy=token_policy(max_chars, False),
                content="没有找到可用字幕。不要读取整段音视频；下一步应人工提供字幕或开启转写。",
                errors=[proc.stderr.strip()[-1000:] if proc.stderr else "subtitle not found"],
            )
        text = vtt_to_text(subtitle_files[0].read_text(encoding="utf-8", errors="replace"))
        content, clipped = cap_text(text, max_chars)
        return ReaderOutput(
            input_type="url",
            source_type="video",
            title=title,
            url=url,
            read_quality="transcript",
            strategy="video_subtitles_only",
            token_policy=token_policy(max_chars, clipped),
            content=content,
            metadata={"subtitle_file": subtitle_files[0].name},
        )


def vtt_to_text(text: str) -> str:
    lines: list[str] = []
    previous = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line or re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = normalize_space(line)
        if line and line != previous:
            lines.append(line)
            previous = line
    return normalize_text("\n".join(lines))


def read_discussion(url: str, max_chars: int) -> ReaderOutput:
    result = read_basic_url(url, max_chars)
    result.source_type = "discussion"
    result.strategy = f"{result.strategy}_discussion_page_only"
    result.read_quality = "basic"
    result.metadata["note"] = "Read page text only; comments may be partial depending on page rendering."
    return result


def read_pdf(url: str, max_chars: int) -> ReaderOutput:
    arxiv_match = re.search(r"arxiv\.org/pdf/([^/?#]+)", url)
    if arxiv_match:
        paper_id = arxiv_match.group(1).removesuffix(".pdf")
        abs_url = f"https://arxiv.org/abs/{paper_id}"
        result = read_basic_url(abs_url, max_chars)
        result.source_type = "paper"
        result.url = url
        result.strategy = "arxiv_pdf_url_to_abs_page"
        result.metadata["read_url"] = abs_url
        result.metadata["paper_id"] = paper_id
        return result

    result = read_basic_url(url, max_chars)
    result.source_type = "pdf"
    if result.content.startswith("%PDF"):
        result.read_quality = "partial"
        result.strategy = "pdf_binary_detected_no_extractor"
        result.content = "检测到 PDF 二进制内容。当前轻量版不解析 PDF；建议后续接入 pdftotext 或 pymupdf，只提取标题、摘要、章节和结论。"
    return result


def read_file(path_text: str, max_chars: int) -> ReaderOutput:
    path = pathlib.Path(path_text).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"file does not exist: {path}")
    if not path.is_file():
        raise RuntimeError(f"not a file: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    content, clipped = cap_text(text, max_chars)
    suffix = path.suffix.lower()
    source_type = "local_file"
    if suffix in {".md", ".markdown"}:
        source_type = "markdown"
    elif suffix in {".txt", ".log"}:
        source_type = "text"
    elif suffix in {".html", ".htm"}:
        title, extracted = extract_html(text)
        content, clipped = cap_text(extracted, max_chars)
        source_type = "html"
    else:
        title = path.stem
    return ReaderOutput(
        input_type="file",
        source_type=source_type,
        title=locals().get("title") or path.stem,
        local_path=str(path),
        read_quality="basic",
        strategy="local_text_file",
        token_policy=token_policy(max_chars, clipped),
        content=content,
        metadata={"suffix": suffix, "size_bytes": path.stat().st_size},
    )


def token_policy(max_chars: int, clipped: bool) -> str:
    suffix = "clipped_head_tail" if clipped else "full_within_budget"
    return f"max_chars={max_chars}; {suffix}"


def effective_max_chars(max_chars: int, read_depth: str) -> int:
    if max_chars != DEFAULT_MAX_CHARS:
        return max_chars
    return READ_DEPTH_BUDGETS[read_depth]


def classify_and_read(
    source: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    mode: str = "fast",
    browser_profile: str = "",
    headless: bool = False,
    interactive_login: bool = False,
    login_timeout_ms: int = 180000,
    read_depth: str = "standard",
) -> ReaderOutput:
    max_chars = effective_max_chars(max_chars, read_depth)
    if not source.startswith(("http://", "https://")):
        return attach_interaction(
            read_file(source, max_chars),
            source,
            read_depth,
            mode,
            browser_profile,
            headless,
            interactive_login,
            login_timeout_ms,
        )

    if mode == "browser":
        if not browser_profile:
            return attach_interaction(
                ReaderOutput(
                    input_type="url",
                    source_type="webpage",
                    title=source,
                    url=source,
                    read_quality="failed",
                    strategy="playwright_persistent_profile",
                    token_policy=token_policy(max_chars, False),
                    content="",
                    errors=["--browser-profile is required when --mode browser is used."],
                ),
                source,
                read_depth,
                mode,
                browser_profile,
                headless,
                interactive_login,
                login_timeout_ms,
            )
        return attach_interaction(
            read_browser_url(
                source,
                max_chars,
                browser_profile,
                headless=headless,
                interactive_login=interactive_login,
                login_timeout_ms=login_timeout_ms,
            ),
            source,
            read_depth,
            mode,
            browser_profile,
            headless,
            interactive_login,
            login_timeout_ms,
        )

    parsed = urllib.parse.urlparse(source)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host in {"github.com", "gist.github.com"}:
        result = read_github(source, max_chars)
        return attach_interaction(result, source, read_depth, mode, browser_profile, headless, interactive_login, login_timeout_ms)
    if "youtube.com" in host or "youtu.be" in host or "bilibili.com" in host:
        result = read_video(source, max_chars)
        return attach_interaction(result, source, read_depth, mode, browser_profile, headless, interactive_login, login_timeout_ms)
    if host in {"news.ycombinator.com", "www.reddit.com", "reddit.com", "v2ex.com", "www.v2ex.com"} or host.endswith(".reddit.com"):
        result = read_discussion(source, max_chars)
        return attach_interaction(result, source, read_depth, mode, browser_profile, headless, interactive_login, login_timeout_ms)
    if path.endswith(".pdf") or "arxiv.org/pdf/" in source:
        result = read_pdf(source, max_chars)
        return attach_interaction(result, source, read_depth, mode, browser_profile, headless, interactive_login, login_timeout_ms)
    result = read_basic_url(source, max_chars)
    should_try_browser = (
        result.read_quality == "blocked"
        or bool(result.metadata.get("maybe_js_rendered"))
    )
    if mode == "auto" and should_try_browser and browser_profile:
        browser_result = read_browser_url(
            source,
            max_chars,
            browser_profile,
            headless=headless,
            interactive_login=interactive_login,
            login_timeout_ms=login_timeout_ms,
        )
        browser_result.metadata["fast_reader"] = {
            "read_quality": result.read_quality,
            "final_url": result.url,
            "maybe_js_rendered": result.metadata.get("maybe_js_rendered", False),
            "errors": result.errors,
        }
        return attach_interaction(browser_result, source, read_depth, mode, browser_profile, headless, interactive_login, login_timeout_ms)
    return attach_interaction(result, source, read_depth, mode, browser_profile, headless, interactive_login, login_timeout_ms)


def to_markdown(result: ReaderOutput) -> str:
    metadata = json.dumps(result.metadata, ensure_ascii=False, indent=2)
    preview = json.dumps(result.preview, ensure_ascii=False, indent=2)
    errors = "\n".join(f"- {error}" for error in result.errors) or "- none"
    actions = "\n".join(
        format_action(action)
        for action in result.next_actions
    ) or "- none"
    return f"""# {result.title}

## Quick Preview

```json
{preview}
```

## Next Operations

{actions}

## Source Reader Metadata

- Input type: {result.input_type}
- Source type: {result.source_type}
- URL: {result.url}
- Local path: {result.local_path}
- Author: {result.author}
- Published: {result.published_at}
- Fetched: {result.fetched_at}
- Reader: {result.reader}
- Read quality: {result.read_quality}
- Strategy: {result.strategy}
- Token policy: {result.token_policy}
- Read depth: {result.read_depth}

## Metadata

```json
{metadata}
```

## Errors

{errors}

## Content

{result.content}
"""


def format_action(action: dict[str, str]) -> str:
    lines = [
        f"- [{action.get('label', action.get('id', 'action'))}] `{action.get('id', '')}`",
        f"  - {action.get('description', '')}",
    ]
    if action.get("command"):
        lines.append(f"  - Command: `{action['command']}`")
    if action.get("prompt"):
        lines.append(f"  - Prompt: {action['prompt']}")
    return "\n".join(lines)


def doctor_to_markdown(report: dict[str, object]) -> str:
    checks = report.get("checks", {})
    if not isinstance(checks, dict):
        checks = {}
    recommendations = report.get("recommendations", [])
    if not isinstance(recommendations, list):
        recommendations = []
    check_lines = "\n".join(
        f"- {key}: {value}"
        for key, value in checks.items()
    )
    recommendation_lines = "\n".join(f"- {item}" for item in recommendations) or "- none"
    return f"""# Source Reader Doctor

- Status: {report.get("status", "unknown")}

## Checks

{check_lines}

## Recommendations

{recommendation_lines}
"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Read one source with a token-aware strategy")
    parser.add_argument("source", nargs="?", help="URL or local file path")
    parser.add_argument("--doctor", action="store_true", help="check source-reader browser/runtime setup")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS, help="maximum content characters to return")
    parser.add_argument("--format", choices=["json", "md"], default="md", help="output format")
    parser.add_argument("--mode", choices=["fast", "browser", "auto"], default="fast", help="read strategy mode")
    parser.add_argument("--read-depth", choices=["preview", "standard", "full"], default="standard", help="reading budget and interaction depth")
    parser.add_argument("--browser-profile", default="", help="persistent browser profile directory for browser/auto mode")
    parser.add_argument("--headless", action="store_true", help="run browser mode headless")
    parser.add_argument("--interactive-login", action="store_true", help="wait for manual login when browser mode reaches an auth page")
    parser.add_argument("--login-timeout-ms", type=int, default=180000, help="manual login wait timeout in milliseconds")
    args = parser.parse_args(argv)

    if args.doctor:
        report = source_reader_doctor(args.browser_profile or ".source-reader/profiles/default")
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(doctor_to_markdown(report))
        return 0 if report.get("status") == "ok" else 1

    if not args.source:
        parser.error("source is required unless --doctor is used")

    try:
        result = classify_and_read(
            args.source,
            args.max_chars,
            mode=args.mode,
            browser_profile=args.browser_profile,
            headless=args.headless,
            interactive_login=args.interactive_login,
            login_timeout_ms=args.login_timeout_ms,
            read_depth=args.read_depth,
        )
    except Exception as exc:
        print(f"source-reader failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(to_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
