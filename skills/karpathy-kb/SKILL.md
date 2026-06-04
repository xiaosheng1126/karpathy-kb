---
name: karpathy-kb
description: Maintain a personal Obsidian knowledge base using the Karpathy LLM-maintained wiki workflow. Use when the user says 读取, 沉淀, 发布, 更新, or asks to read sources with source-reader and decide whether they should become durable wiki knowledge.
---

# Karpathy KB

You maintain the user's Obsidian knowledge base. The goal is not to save every source, but to turn useful sources into durable, reusable wiki notes after user confirmation.

## Intent

- `读取 <source>`: read for the current task only. Do not create raw notes or update wiki.
- `沉淀 <source>`: read the source, create a raw note, add summary/advice/questions in raw, then ask for confirmation.
- `发布`: only after explicit confirmation, update wiki/index/log and mark the raw note as `published`.
- A bare link is not enough to deposit. If intent is unclear, read for the current task only.

## Commands

Run from the knowledge base root.

```bash
python3 scripts/source_reader.py remote-read <source> --read-depth preview --format md
python3 scripts/source_reader.py <source> --mode auto --browser-profile .source-reader/profiles/default --interactive-login --login-timeout-ms 180000 --read-depth preview --format md
python3 scripts/kb.py raw <source> --read-depth standard
python3 scripts/kb.py raw <source> --mode auto --browser-profile .source-reader/profiles/default --interactive-login --login-timeout-ms 180000 --read-depth standard
python3 scripts/kb.py review <raw-file>
python3 scripts/kb.py publish-prompt <raw-file>
python3 scripts/install.py --target both --install-runtime --install-mcp --start-service
python3 scripts/source_reader.py --doctor --format md
```

Prefer the MCP tool when available. If MCP is not configured, use `remote-read`: it calls the local source-reader service on `127.0.0.1`, while the service owns external networking, Playwright, cache, and browser profiles. If the service is unavailable, start it with `python3 scripts/source_reader.py serve --host 127.0.0.1 --port 8765` or fall back to the direct auto-mode command.

Use auto mode for JS-rendered pages, login-gated pages, Yuque, Feishu, Notion, Knowledge Star, and similar sources. Reuse `.source-reader/profiles/default` for persistent login state. If Playwright is missing, run the installer command above once instead of asking the user which retry path to take.
If browser reading still fails, run `source_reader.py --doctor` and follow explicit setup recommendations before asking the user.

After each read, inspect `actions` / `Next Operations` first. Treat them as the supported button protocol:

- Execute `login_with_browser` when auth is required.
- Execute `continue_deep_read`, `extract_outline`, or `extract_code` when the user asks to continue in that direction.
- Use `summarize_for_kb` for review advice, but do not write wiki.
- Use `save_raw` only when the user says to deposit.
- Use `mark_result_good` / `mark_result_bad` when the user gives feedback about read quality.
- Do not invent a separate retry flow if an action already covers it.

## Rules

- Persist only `fetched` and `published`. Do not write `reviewed` or `approved` as file states.
- Raw notes are the source workspace. Keep metadata, read quality, original content or traceable excerpts, auto summary, suggestions, wiki targets, and confirmation questions.
- Do not create `wiki/sources/*.md` as a temporary summary.
- Wiki notes are topic-oriented. Prefer updating existing wiki pages over creating duplicates.
- Do not publish until the user explicitly confirms.
- When reading large content, start with `--read-depth preview`, summarize what was found, and ask whether to deep-read, deposit raw, or answer a focused question.

## Project Files

- Read `AGENTS.md` for the full maintenance protocol.
- Read `commands.md` for trigger behavior.
- Read `profile.md` before giving advice or publishing.
- Use `source-reader/README.md` when changing source-reader behavior.
