# Contributing

Thanks for contributing to Intern Radar.

## Development Setup

Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Frontend:

```bash
cd internradar/dashboard/frontend
npm install
npm run build
cd ../../..
```

## Core Commands

```bash
internradar init --local
internradar firms validate --pack quant_engineering
internradar scan --pack quant_engineering --dry-run
internradar dashboard
internradar review --limit 10
internradar export --format html
internradar discover queries --pack quant_engineering --limit 10
```

## Test Commands

```bash
python3 -m unittest discover -s tests -p 'test*.py' -v
.venv/bin/pytest
python3 -m ruff check .
```

If `ruff` is not installed in your active environment, reinstall with:

```bash
pip install -e ".[dev]"
```

## Contribution Guidelines

- Keep the core system domain-agnostic.
- Put pack-specific knowledge under `packs/<pack_name>/`.
- Do not add private specs or personal notes to the repository.
- Do not add tests that hit live network endpoints.
- Prefer evidence-based parsing and scoring over silent assumptions.
- Preserve user actions and overrides across scans.
- Keep the FastAPI + Svelte dashboard direction intact.

## Pull Request Expectations

- Add or update tests for behavior changes.
- Document user-facing changes in the README or `docs/` when relevant.
- Keep CLI failures helpful and explicit.
- Avoid large unrelated rewrites.

## Reporting Issues

Use the issue templates in `.github/ISSUE_TEMPLATE/`:

- bug report
- feature request
- add firm
