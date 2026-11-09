# Decisions log

Every decision about a source, a rule or the system, with the date, what was decided and why (PRD 16.4).

## 2026-11-08

- **Repo created private.** dhen2012/gov-bid-engine. Private until Dakota decides where the page lives (PRD decision on the page home). Switching to public later is one setting.
- **Language and tools confirmed for phase 0.** Python 3.12, requests, pytest, GitHub Actions. Playwright is added when the first collector that needs a real browser is built (phase 2).
- **Daily schedule.** 03:37 UTC every day (10:37 pm Eastern in winter). Late evening so bids posted during the business day are in that night's run, inside the 26 hour freshness target.
- **Page is one self contained HTML file.** Data is embedded in the page, so the same file works as a hosted page or a file opened by double click (WEB 3). Revisit when the bid count makes the file too large (STO 2).
- **Each collector runs in its own process with a time limit** (COL 2, COL 3), started from the sources table (CFG 1). Turning a source on is one cell in config/sources.csv.
- **Reach test sample.** 20 pages from the Opus checked verified pages file (Confirmed or Corrected rows only), one page per host, spread across listing types (10 html list, 5 pdf links, 2 news posts, 3 embedded portal), picked by a hash of the entity ID so the sample never changes by accident. Built by scripts/make_reach_sample.py.
- **Reach test runs every night during phase 0 and stays on as a health check** until the phase 2 collector replaces it.
- **Reach test rules.** robots.txt is read first and respected, honest user agent, 2 seconds between requests to a host, retries only on timeouts and server errors, never on 401, 403, 429 or a challenge page.
- **Outside code reuse (Dakota, 2026-11-08).** Before any collector is built: Opus reads jasonstaker/rfp-scraper (MIT) and lists which scrapers still work; only those are copied, with the copyright notice kept in THIRD_PARTY_NOTICES. dobtco/openrfps (GPL 3.0) is read only to learn sources and page patterns, never copied. For each shared platform (BidNet Direct, Bonfire, PlanetBids, OpenGov, SCBO), price the matching paid Apify scraper with one small test run Dakota approves first, compare to the live platform, then put rent or build to Dakota with monthly cost and tradeoffs. Every reuse and rent or build call is logged here.
