# kb-site

Personal knowledge dashboard for `karpathy-kb`.

## Quickstart

```bash
# 1. From repo root, generate data indexes
python3 scripts/kb.py generate-index

# 2. Install deps (first time only)
cd kb-site && npm install

# 3. Build static site
npm run build

# 4. Preview
npm run preview
```

## Dev mode

```bash
python3 scripts/kb.py generate-index  # run from repo root first
cd kb-site && npm run dev
```

Data is read from `../generated/*.json` at build time. Re-run `generate-index`
whenever wiki or role files change.
