# Gov Bid Engine

Collects public government solicitations every day, tags each with NAICS codes, and publishes a searchable page. Public sources only. Requirements: Gov-Bid-Engine-PRD-2026-11-08.md in Dakota's project folder.

## How it runs
- `.github/workflows/daily.yml` runs every day at 03:37 UTC and can be started by hand.
- Tests run first. A failing test stops the run before anything is published.
- `engine/run_daily.py` runs each enabled source in `config/sources.csv` in its own process with a time limit, then the reach test.
- `engine/build_page.py` builds `public/index.html`, one self contained page with the data inside it.
- Data, run records and the page are committed back to this repo by the run.

## Secrets
Added by Dakota in GitHub, Settings, Secrets and variables, Actions. Never in code or files.
- `SAM_GOV_API_KEY` (phase 1)

## Layout
- `config/` sources table, reach test sample, verified SC bid pages
- `collectors/` one module per source type
- `engine/` run, health, reach test, page build
- `site/` page template
- `data/` runs, reach test results, bid index
- `docs/` decisions, source reviews, session closes
