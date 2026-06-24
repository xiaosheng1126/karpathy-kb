# kb-site Isolation Rules

This directory is a read-only visualization layer over `karpathy-kb`. These rules
are enforced for all agents, scripts, and humans working in this directory.

## What kb-site may read
- `../generated/*.json` — only via `src/lib/kb-data.ts`, not directly in components

## What kb-site must never do
- Read `../wiki/`, `../raw/`, `../index.md`, `../log.md` directly from source
- Write to any file outside `kb-site/`
- Commit files from `generated/` or `dist/`

## Build order
1. `python3 scripts/kb.py generate-index` (from repo root)
2. `cd kb-site && npm run build`

## Data contract
All types are defined in `src/lib/kb-data.ts`. The JSON schema is in
`docs/superpowers/specs/2026-06-23-kb-site-phase0-phase1-design.md`.
