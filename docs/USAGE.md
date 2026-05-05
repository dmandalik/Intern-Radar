# Usage

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
internradar init --local
```

## Validate a Pack

```bash
internradar firms validate --pack quant_engineering
```

## Scan Examples

Dry run:

```bash
internradar scan --pack quant_engineering --dry-run --max-firms 10
```

Focused company scan:

```bash
internradar scan --pack quant_engineering --company "Hudson River Trading"
```

Verbose scan:

```bash
internradar scan --pack quant_engineering --max-firms 10 --verbose
```

## Dashboard Launch

```bash
internradar dashboard
```

Optional:

```bash
internradar dashboard --open-browser
```

## Frontend Build

If the dashboard says the frontend assets are missing:

```bash
cd internradar/dashboard/frontend
npm install
npm run build
cd ../../..
```

## Review Examples

```bash
internradar review --limit 15
internradar review --status unknown
internradar review --hidden-gems
internradar review --all
```

## Discovery Examples

Generate search queries:

```bash
internradar discover queries --pack quant_engineering --limit 25
internradar discover queries --pack quant_engineering --season "Summer 2027" --role "Software Engineer Intern" --domain greenhouse
```

Export generated queries:

```bash
internradar discover queries --pack quant_engineering --output queries.json --format json
```

Import a local markdown internship list:

```bash
internradar discover import-github --path data/samples/sample_jobs.md --pack quant_engineering
```

## Filtering Examples

Dashboard filtering is available through the local UI. Export filtering is available in the CLI:

```bash
internradar export --format xlsx --status open
internradar export --format html --hidden-gems
internradar export --format markdown --saved
internradar export --format csv --applied
```

## Troubleshooting

No database found:

- run `internradar init --local`
- then run a scan

Dashboard assets missing:

- run `npm install`
- run `npm run build` in `internradar/dashboard/frontend`

No jobs to export:

- run a scan first
- verify with `internradar dashboard` or `internradar review`

Pack validation failed:

- inspect the relevant YAML in `packs/<pack_name>/`
- run `internradar firms validate --pack <pack_name>`
