---
name: karpathy-kb
description: Maintain a personal Obsidian knowledge base using the Karpathy LLM-maintained wiki workflow. Use when the user says 读取, 沉淀, 发布, 更新, or asks to read sources and decide whether they should become durable wiki knowledge. Reader functionality is provided by the standalone source-reader MCP server.
---

# Karpathy KB

You maintain the user's Obsidian knowledge base. The goal is not to save every source, but to turn useful sources into durable, reusable wiki notes after user confirmation.

## Intent

- `读取 <source>`: read for the current task only. Do not create raw notes or update wiki.
- `沉淀 <source>`: read the source, create a raw note, add summary/advice/questions in raw, then ask for confirmation.
- `发布`: only after explicit confirmation, update wiki/index/log and mark the raw note as `published`.
- A bare link is not enough to deposit. If intent is unclear, read for the current task only.

## Source Reader

Reading URLs / PDFs / video transcripts / login-gated pages is owned by the standalone `~/Documents/source-reader/` project, registered as MCP server `source-reader`. This repo no longer ships a reader implementation.

Prefer the MCP tools:

- `source_reader_read` — read a source.
- `source_reader_action` — run follow-up actions (`login_with_browser`, `continue_deep_read`, `extract_outline`, `extract_code`, `mark_result_good`, `mark_result_bad`).
- `source_reader_feedback` — record read-quality feedback.

If the MCP server is unhealthy, diagnose from the standalone repo (`cd ~/Documents/source-reader && python3 scripts/source_reader.py status`). Do not fall back to Claude's built-in Fetch / WebFetch.

## Commands

Run from the knowledge base root.

```bash
python3 scripts/kb.py raw <source>                                 # via local source-reader service, write raw
python3 scripts/kb.py raw <source> --mode auto --interactive-login --read-depth standard
python3 scripts/kb.py list --status fetched
python3 scripts/kb.py review <raw-file>
python3 scripts/kb.py publish-prompt <raw-file>
```

`kb.py raw` calls `127.0.0.1:8765` (the standalone source-reader service). If the service is down:

```bash
cd ~/Documents/source-reader && python3 scripts/source_reader.py serve --host 127.0.0.1 --port 8765
```

For pure reading (no raw write), call MCP `source_reader_read` directly — don't invoke local scripts.

After each read, inspect `actions` / `Next Operations` first. Treat them as the supported operation protocol. Prefer `scope=reader` actions for generic reading, and only use `scope=adapter` actions inside the karpathy-kb workflow:

- Execute `login_with_browser` (`reader`) when auth is required.
- Execute `continue_deep_read`, `extract_outline`, or `extract_code` (`reader`) when the user asks to continue in that direction.
- Use `mark_result_good` / `mark_result_bad` (`reader`) when the user gives feedback about read quality.
- Use `summarize_for_kb` (`adapter:karpathy-kb`) for review advice, but do not write wiki.
- Use `save_raw` (`adapter:karpathy-kb`) only when the user says to deposit.
- Do not invent a separate retry flow if an action already covers it.

## Rules

- Persist only `fetched` and `published`. Do not write `reviewed` or `approved` as file states.
- Raw notes are the source workspace. Keep metadata, read quality, original content or traceable excerpts, auto summary, suggestions, wiki targets, and confirmation questions.
- **After `kb.py raw` creates a raw file, immediately edit it to fill Auto Summary, Suggestions, and `wiki_targets` — never leave placeholders. Present the summary to the user only after the raw is complete.**
- Do not create `wiki/sources/*.md` as a temporary summary.
- Wiki notes are topic-oriented. Prefer updating existing wiki pages over creating duplicates.
- Do not publish until the user explicitly confirms.
- When reading large content, start with `read_depth=preview` (MCP) or `--read-depth preview` (kb.py), summarize what was found, and ask whether to deep-read, deposit raw, or answer a focused question.
- When publishing, always perform "weave-back": scan `index.md`, identify all related existing wiki pages, and update them before writing the current topic. One new source may touch multiple existing pages.

## Project Files

- Read `AGENTS.md` for the full maintenance protocol.
- Read `commands.md` for trigger behavior.
- Read `profile.md` before giving advice or publishing.
- For source-reader design / operations, see `~/Documents/source-reader/README.md` and `~/Documents/source-reader/CLAUDE.md`.
