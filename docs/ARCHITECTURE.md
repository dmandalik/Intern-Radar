# Architecture

Intern Radar is a local-first pipeline that starts at public job sources and ends in a local database, dashboard, and export layer.

## CLI

The command surface lives in `internradar/cli.py` and `internradar/commands/`.

Key commands:

- `init`
- `firms`
- `scan`
- `review`
- `dashboard`
- `export`
- `discover`

## Config System

Config is loaded from:

1. bundled defaults in `configs/default_preferences.yaml`
2. `~/.internradar/config.yaml`
3. `./.internradar/config.yaml`

Manual overrides are loaded separately from:

- `~/.internradar/overrides.yaml`
- `./.internradar/overrides.yaml`

## Domain Packs

Packs live in `packs/<pack_name>/` and contain:

- `firms.yaml`
- `role_keywords.yaml`
- `prestige_tiers.yaml`
- `source_queries.yaml`

The first pack is `quant_engineering`.

## Collectors

Collectors live in `internradar/collectors/`.

Implemented source families:

- Greenhouse
- Lever
- custom public career pages
- GitHub markdown list import for secondary discovery

Collectors return `RawJob` objects only. They do not normalize, classify, score, or persist jobs.

## Normalization Pipeline

The scan flow:

1. load pack firms
2. select matching collectors
3. collect `RawJob` objects
4. normalize to `Job`
5. classify role
6. parse eligibility
7. infer status
8. deduplicate
9. score
10. apply manual overrides
11. persist jobs and snapshots

## Parsers

Parsers live in `internradar/parsers/`.

Implemented responsibilities:

- HTML/text cleaning
- season/year parsing
- location parsing
- job normalization and stable IDs
- role classification
- eligibility parsing

## Verification

Verification helpers live in `internradar/verification/`.

Implemented pieces:

- status checker
- URL canonicalization
- page/content hashes
- duplicate detection and merge

## Scoring

Scoring modules live in `internradar/scoring/`.

Implemented score components:

- prestige
- role fit
- technical depth
- freshness
- eligibility
- hidden gems
- weighted opportunity score presets

## Database

SQLite persistence lives in `internradar/core/database.py`.

Tables:

- `scan_runs`
- `companies`
- `jobs`
- `user_actions`
- `job_snapshots`

This database is local to `.internradar/internradar.sqlite3`.

## Review Workflow

Review helpers live in `internradar/review/`.

Implemented pieces:

- persistent user actions
- manual overrides
- review queue generation
- terminal review mode
- dashboard action compatibility

## Dashboard Backend

The local dashboard API lives in `internradar/dashboard/api.py` and `internradar/dashboard/backend.py`.

The backend reads the same SQLite database as the CLI and serves:

- summary metrics
- job lists
- filters
- job details
- review state
- export actions

## Dashboard Frontend

The frontend lives in `internradar/dashboard/frontend/`.

Stack:

- Svelte
- Vite
- TypeScript
- Tailwind CSS

The built `dist/` assets are served by FastAPI for local use.

## Exports

Export modules live in `internradar/export/`.

Supported outputs:

- CSV
- JSON
- XLSX
- HTML
- Markdown
