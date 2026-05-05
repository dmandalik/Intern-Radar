# UI Design

Intern Radar uses a custom local FastAPI + Svelte/Vite dashboard.

## Why Not Streamlit

- Streamlit encourages a notebook-app feel that does not fit a persistent internship workflow product.
- Intern Radar needs stronger control over navigation, dense review flows, drawer interactions, and visual polish.

## Why Not React

- React was intentionally not chosen for this local dashboard.
- Svelte keeps the frontend smaller and easier to reason about for a local product with focused interactions.

## Why Svelte / Vite

- fast local iteration
- compact component model
- good fit for an offline-feeling local app
- straightforward static build output that FastAPI can serve

## Backend / Frontend Split

- FastAPI serves local data and actions from SQLite
- Svelte/Vite renders the dashboard UI
- built frontend assets are served by the backend

## Local-First Architecture

- SQLite is the primary app store
- notes and actions persist locally
- no hosted dashboard dependency
- exports are generated from local data

## Theme Tokens

Dark / dusk default:

- `--bg: #0f0d14`
- `--bg-soft: #15111d`
- `--surface: #17131f`
- `--surface-2: #211b2b`
- `--surface-glass: rgba(255,255,255,0.045)`
- `--border: rgba(255,255,255,0.08)`
- `--border-strong: rgba(255,255,255,0.16)`
- `--text: #f3eee7`
- `--muted: #a79cae`
- `--muted-2: #7f7388`
- `--accent: #c8ff6b`
- `--accent-2: #b89cff`
- `--warning: #ffd166`
- `--danger: #ff6b6b`
- `--success: #86efac`
- `--info: #93c5fd`

Light / dawn optional:

- `--bg: #fef6f0`
- `--bg-soft: #f8eadf`
- `--surface: #fffaf5`
- `--surface-2: #fceee4`
- `--surface-glass: rgba(255,255,255,0.65)`
- `--border: rgba(45,31,26,0.10)`
- `--border-strong: rgba(45,31,26,0.18)`
- `--text: #2d1f1a`
- `--muted: #7d6b62`
- `--muted-2: #9a877d`
- `--accent: #7a9f2b`
- `--accent-2: #7c5cff`
- `--warning: #b7791f`
- `--danger: #c2410c`
- `--success: #15803d`
- `--info: #2563eb`

## Typography Roles

- display headings: editorial, high-contrast
- body copy: compact and readable
- mono labels: technical metadata, timestamps, status, and score context

## Component Language

- score pills look calibrated and compact
- status pills communicate state quickly
- hidden gem cards feel like “signal found” cards
- evidence drawers feel like audit trails

## Dashboard Pages

- Overview
- Jobs
- Hidden Gems
- Coming Soon
- Saved
- Review
- Settings
- Export

## Design Principles

- evidence-first workflows
- warm surfaces instead of cold flat blacks
- clear hierarchy
- restrained motion
- readable density for laptop screens
- accessibility through contrast, spacing, and explicit labels

## Inspiration

The visual direction is inspired by modern AI and productivity tools:

- time-of-day themes
- editorial headings
- mono technical labels
- warm surfaces
- refined minimalism

It does not claim affiliation with any external company and does not copy external assets, logos, or brand systems.
