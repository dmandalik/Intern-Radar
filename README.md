# Intern Radar

Intern Radar is a local-first internship intelligence tool that helps students discover open roles, parse eligibility, rank opportunities by personal preferences, identify hidden gems, track changes between scans, and export polished application lists.

It is designed as a personal command center rather than a static internship spreadsheet. Intern Radar scans public career sources, normalizes results into a local SQLite database, applies evidence-based parsing and scoring, exposes a custom FastAPI + Svelte dashboard, and keeps your review workflow on your machine.

## Why Local-First

- Your scan history, notes, saved jobs, and applied states stay in local files.
- No API keys are required for the core workflow.
- You can inspect and export your own data without depending on a hosted service.
- You can customize domain packs, ranking preferences, and manual overrides directly from the repo.

## What It Tracks Today

- Known firms from domain packs
- Public Greenhouse, Lever, and custom career pages
- Normalized jobs with role classification, eligibility parsing, status evidence, duplicate merging, and scoring
- Saved/applied/reviewed/ignored workflow state
- Search discovery query generation
- Public GitHub internship-list import for secondary discovery
- Polished CSV, JSON, Excel, HTML, and Markdown exports

## Why It Is Different From Static Internship Lists

- It tracks live public listings instead of only curated markdown tables.
- It stores normalized job records with timestamps, evidence, and score explanations.
- It lets you review ambiguous jobs instead of silently dropping them.
- It distinguishes hidden gems from merely obscure low-quality roles.
- It includes a local dashboard, review workflow, and export system instead of just a list of links.

## Features

- Local SQLite database with scan runs, jobs, job snapshots, and user actions
- Domain packs, starting with `quant_engineering`
- Greenhouse, Lever, custom career page, and GitHub list discovery support
- Role classification with confidence and evidence
- Eligibility parsing with confidence and raw evidence
- Status checking with explainable signals
- Duplicate detection and merge logic
- Opportunity scoring, ranking presets, and hidden gems mode
- Manual review queue, persistent overrides, and notes
- Custom FastAPI + Svelte/Vite dashboard
- Search discovery query generation with no paid APIs
- CSV, JSON, XLSX, HTML, and Markdown export outputs

## Installation

Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Frontend build prerequisites for the dashboard:

```bash
cd internradar/dashboard/frontend
npm install
npm run build
cd ../../..
```

The dashboard command serves the built frontend assets directly. If the assets are missing, `internradar dashboard` will tell you to build them first.

## Quickstart

```bash
internradar init --local
internradar firms validate --pack quant_engineering
internradar scan --pack quant_engineering --max-firms 10
internradar dashboard
internradar export --format xlsx
internradar export --format html
```

Real scans use current public job pages and ATS boards, so results vary based on what is live when you run them.

## Example Commands

Initialize local state:

```bash
internradar init --local
```

Inspect the quant firm universe:

```bash
internradar firms list --pack quant_engineering
internradar firms search "HRT" --pack quant_engineering
```

Run a dry scan:

```bash
internradar scan --pack quant_engineering --dry-run --max-firms 10
```

Run a real scan:

```bash
internradar scan --pack quant_engineering --max-firms 10 --verbose
```

Review uncertain or high-signal jobs:

```bash
internradar review --limit 20
internradar review --hidden-gems
internradar review --status unknown
```

Generate manual discovery queries:

```bash
internradar discover queries --pack quant_engineering --limit 25
internradar discover queries --pack quant_engineering --season "Summer 2027" --domain greenhouse --output queries.txt
```

Import a public markdown internship list from disk:

```bash
internradar discover import-github --path path/to/list.md --pack quant_engineering
```

Export ranked jobs:

```bash
internradar export --format csv
internradar export --format json --hidden-gems
internradar export --format xlsx --applied
internradar export --all
```

## Custom Dashboard

Intern Radar ships with a custom local dashboard built with FastAPI on the backend and Svelte/Vite on the frontend.

- Default URL: `http://127.0.0.1:8765`
- Backend: local API over the same SQLite database used by the CLI
- Frontend: polished Svelte UI with dusk/dawn theming, score pills, evidence drawers, and workflow pages

Launch it with:

```bash
internradar dashboard
```

Optional:

```bash
internradar dashboard --open-browser
```

The dashboard supports:

- Overview metrics and scan summaries
- Search, filters, and sorting
- Hidden gems and coming-soon views
- Saved/applied/review queues
- Notes and workflow state
- Export actions

## Export Examples

Exports are written to `.internradar/exports/` by default unless you pass `--output`.

```bash
internradar export --format html
internradar export --format markdown --saved
internradar export --format xlsx --status open --limit 50
```

Generated formats:

- CSV
- JSON
- Excel/XLSX
- HTML report
- Markdown report

## Domain Packs

Domain packs keep role-specific knowledge outside the core pipeline. A pack can define:

- firms
- role keywords
- prestige tiers
- manual source query templates

The core system remains domain-agnostic. Domain-specific logic belongs in `packs/<pack_name>/`.

## Quant Engineering Pack

The first pack is `quant_engineering`. It focuses on technical quant-adjacent internships such as:

- trading systems engineering
- quant development
- low-latency systems
- market data engineering
- infrastructure engineering
- FPGA and hardware acceleration
- research engineering

It includes:

- 50+ firms
- pack-driven role keyword configuration
- prestige tiers
- discovery query templates

## Hidden Gems

Hidden gems mode looks for roles that are:

- technically relevant
- reasonably fresh and still actionable
- credible rather than spammy
- less obvious than top-tier saturated listings

The score is transparent and evidence-based. A role does not become a hidden gem just because it is obscure.

## Eligibility Parser

Intern Radar parses job descriptions for:

- degree levels
- graduation years and ranges
- class years
- majors
- sponsorship signals
- citizenship and ITAR restrictions
- minimum GPA

Unknown remains unknown. The parser is conservative by design and records evidence snippets for what it did find.

## Search Discovery

Intern Radar includes offline/manual discovery support:

- pack-driven search query generation
- optional query export to text, JSON, or CSV
- GitHub markdown internship-list import
- unknown-company comparison against the current firm pack

This improves niche-firm discovery without requiring paid search APIs or API keys.

## Architecture Overview

High-level layers:

- CLI commands in `internradar/commands/`
- config and path helpers in `internradar/core/`
- domain packs in `packs/`
- collectors in `internradar/collectors/`
- normalization and parsing in `internradar/parsers/`
- verification in `internradar/verification/`
- scoring in `internradar/scoring/`
- review workflow in `internradar/review/`
- exports in `internradar/export/`
- dashboard backend/frontend in `internradar/dashboard/`

More detail:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/USAGE.md](docs/USAGE.md)
- [docs/UI_DESIGN.md](docs/UI_DESIGN.md)

## UI / Design Philosophy

Intern Radar deliberately avoids the generic “data science app” look.

- Not Streamlit
- Not React
- FastAPI + Svelte/Vite
- Dusk-first dashboard theme with an optional dawn mode
- Editorial hierarchy, mono technical labels, evidence-first panels
- Calm, local-product feel rather than template-dashboard styling

See [docs/UI_DESIGN.md](docs/UI_DESIGN.md).

## Ethical Crawling Policy

Intern Radar only targets public sources and avoids hostile automation.

- Public pages only
- No login bypass
- No CAPTCHA bypass
- No auto-apply behavior
- Local-first storage
- Respectful collection behavior and user-agent configuration

See [docs/ETHICAL_CRAWLING.md](docs/ETHICAL_CRAWLING.md).

## Demo / Sample Data

Artificial sample artifacts live in `data/samples/`:

- `sample_jobs.json`
- `sample_report.html`

These are synthetic examples for demos and screenshots, not live scraped data.

## Acceptance Snapshot

Current v1 status:

- `internradar init` works
- `internradar scan --pack quant_engineering` runs through the full local pipeline
- 50+ firms load from the quant pack
- Greenhouse, Lever, and custom-page collectors are tested
- Jobs normalize into the local database
- Role, eligibility, status, duplicate detection, scoring, and hidden gems are implemented
- Dashboard launches locally from built Svelte assets
- Save/ignore/applied workflow persists
- Export formats work
- Search discovery and GitHub list import work

Partial / documented limitations:

- No paid search API integrations
- No live-network tests in CI
- No hosted multi-user deployment story
- Scan history comparison is present in stored scan summaries, but deeper trend UX is still light

## Limitations

- Public listings can disappear, change structure, or close between scans.
- Some custom career pages are intentionally conservative to avoid noisy false positives.
- GitHub list import is a discovery aid, not a source of truth for job status.
- Manual review is terminal-first today; rich field editing in the dashboard is still limited.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
