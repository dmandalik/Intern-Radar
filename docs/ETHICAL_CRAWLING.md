# Ethical Crawling

Intern Radar is designed for respectful, public, local-first internship discovery.

## Rules

- Public pages only
- No login bypass
- No CAPTCHA bypass
- No scraping of private data
- No auto-apply actions
- No recursive unrestricted crawling

## ATS and Career Pages

Intern Radar prefers structured public ATS sources when available:

- Greenhouse
- Lever
- public custom career pages

Custom-page collection is intentionally conservative and depth-limited.

## Request Behavior

- Use timeouts
- Support user-agent configuration
- Support polite delays
- Prefer bounded scans over wide scraping

## Robots and Site Boundaries

Where feasible, respect `robots.txt` and obvious site boundaries.

Intern Radar is not designed to evade platform controls or access restrictions.

## Local-First Storage

Collected data is stored locally in SQLite. Notes, review actions, overrides, and exports stay on the user’s machine unless the user explicitly shares them.

## Human Review

If a role is ambiguous, the system should surface it for review rather than over-claim certainty.
