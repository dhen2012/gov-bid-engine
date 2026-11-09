# Source review: SAM.gov Contract Opportunities (PRD SRC 1 to SRC 6)

Reviewed 2026-11-08. Research by a Sonnet agent (official pages only), data services page checked by the main session in Chrome. Nothing below was tested with a live API call yet; those items are marked unverified.

## Channel
- Official API: https://api.sam.gov/opportunities/v2/search (Get Opportunities Public API, open.gsa.gov). Channel shown on the status panel: API.
- Backup and comparison channel: the public file extract ContractOpportunitiesFullCSV.csv in SAM.gov Data Services, folder Contract Opportunities / datagov, marked Public, "Date Modified Nov 07, 2026" (seen in Chrome 2026-11-08). The download link is built by the page's script; the direct download address and the file size are unverified. To be probed from GitHub Actions in phase 1.

## Terms (https://sam.gov/about/terms-of-use)
- "Automated data gathering, web scraping tools are prohibited." So the website is never scraped. We use the API and, if needed, the published public extract file.
- "If you want to share data publicly, only share data from public versions of APIs." We use only the public API, so showing the notices on our page fits this.
- "Do not share your individual account API key with anyone." The key lives only in the GitHub secret SAM_GOV_API_KEY, is never printed, and is scrubbed from every error message (collectors/sam_gov.py, tested in tests/test_phase1.py).
- "Update your API key and system account password every 90 days." The key must be replaced about every 90 days. When the key stops working the collector logs the 401 or 403 and the status panel flags SAM.gov the same night. A dated reminder is added once Dakota says the day he created the key.
- Attribution is requested, not required: "Citation of the GSA site and a link back is much appreciated." The page links every SAM bid back to sam.gov.
- No official page says in plain words that republishing notices on a private search page is allowed. Reading of the terms above: it fits "public versions of APIs". Recorded as a judgment, not a confirmed permission.

## robots.txt
- sam.gov/robots.txt: summarized by the fetch tool, does not appear to block /opp/. Not confirmed line by line.
- api.sam.gov/robots.txt: could not be fetched. The API's own terms govern API use (COL 12).
- Both to be fetched from GitHub Actions in phase 1.

## Limits
- The Opportunities API page gives no numbers ("limited based on the federal or non-federal or general roles").
- The Entity API page gives: non federal user with no role, 10 requests a day; with a role, 1,000 a day; system account, 1,000 a day. Unverified for this API.
- Design: the collector caps itself at 8 requests a day (SAM_MAX_REQUESTS) and records the X-RateLimit headers on every run, so the real limit is measured (phase 1 acceptance).
- One page holds up to 1,000 notices. A 2 day posted window is expected to need about 3 to 6 requests. Unverified until the first run.

## Fields
- Read both spellings of the deadline: responseDeadLine and reponseDeadLine.
- description is a link that needs the key appended and costs one request per notice. Not fetched in phase 1 (would blow the daily limit).
- ptype codes: u justification, p presolicitation, a award, r sources sought, s special notice, o solicitation, g surplus sale, k combined synopsis/solicitation, i intent to bundle. f and l are retired.

## Public listing link
- The API's uiLink needs a contracting role. The collector builds https://sam.gov/opp/<noticeId>/view instead.
- Conflict: the API page warns a logged out user gets a 404, but search engines index these pages. Unverified. Phase 1 acceptance opens 20 random links logged out.

## Login, captcha, block
- None for the API with a key. BLK 2 risk from GitHub addresses: unknown until the first run.

## Decision
- Collect with the public API daily. Compare daily counts to the public extract file. Never scrape sam.gov pages.
