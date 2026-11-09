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

## 2026-11-08 (later)

- **Page home: GitHub Pages, public repo (Dakota).** Free and one link. Tradeoff: the repo and the page are public to anyone who has the link. The data is public bids only. The page carries a noindex tag, which is what keeps it out of search engines (WEB 4). A robots.txt is also published, but it sits under /gov-bid-engine/ and crawlers only read robots.txt at the site root, so it has no effect; checked live in Chrome 2026-11-08. No keys are ever in the repo.
- **Reach test, first result (manual test run 42553179493).** 18 of 20 load from GitHub. Town of Ravenel returned a 403 challenge page (BLK 2, data center traffic turned away). City of Pickens closed the connection before answering, on both robots.txt and the page (not yet classed; watch on the scheduled run). Both go to the BLK 2 path in phase 2: look for an email alert or RSS channel, else manual in Chrome.

- **NAICS tagging for bids with no code (Dakota).** Free rules first (crosswalks and keyword rules). Measure how many bids stay untagged, then decide on AI tagging with real numbers.
- **First shared platform after South Carolina (Dakota).** The one with the most agencies whose listings are public, decided after the source reviews (PRD default).
- **Daily email alerts (Dakota).** Phase 6, as planned.
- **Paid Apify test runs (Dakota).** Ask before every test run: name the scraper, the run size and the most it can cost, and wait for a yes. No standing approval.
- **Outside code review result (Opus, 2026-11-08).** rfp-scraper (MIT, Copyright (c) 2025 Jason Staker): 89 scrapers, 25 with useful patterns (SCBO, Bonfire feed, OpenGov API, 7 state data feeds), none for SAM.gov. Not copied as is: every scraper sends a fake browser user agent (breaks COL 14), 48 need Selenium on Windows, the SC one turns off TLS checks, and the author says it is unmaintained. Rule: reuse the source knowledge, rewrite the code in our collectors, keep the MIT notice in THIRD_PARTY_NOTICES for any file adapted from it. OpenRFPs (GPL 3.0, 2014) used only as a source list; all its URLs have moved. Full notes: research/Gov-Bid-Engine-reuse-review-2026-11-08.md in Dakota's project folder.
