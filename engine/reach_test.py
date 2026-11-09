"""PRD BLK 9: reach test from GitHub Actions.

Loads a fixed sample of 20 SC agency bid pages (config/reach_test_sample.csv)
and records, for each, whether it loads or is turned away. This measures
BLK 2 (data center traffic turned away) before any collector depends on it.

Rules followed (PRD 8.4): robots.txt is checked first, one request per page,
at least 2 seconds between requests to the same host, an honest user agent,
up to 3 retries with growing waits on timeouts, connection errors and 5xx,
and never a retry on 401, 403, 429 or a challenge page. Nothing here tries
to get past a block.
"""
import csv
import re
import sys
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

from engine.common import CONFIG, DATA, USER_AGENT, now_utc, today_et, write_json

SAMPLE = CONFIG / "reach_test_sample.csv"
TIMEOUT = 30
RETRIES = 3
PACE = 2.0

CHALLENGE_MARKERS = [
    "just a moment",
    "cf-chl",
    "attention required",
    "captcha",
    "are you a robot",
    "access denied",
    "request unsuccessful. incapsula",
    "_incapsula_resource",
]
LOGIN_MARKERS = [r'type=["\']?password', r"\bsign in to continue\b", r"\blog ?in required\b"]

# Outcome labels shown in the report.
LOADS = "loads"
TURNED_AWAY = "turned away"
CHALLENGE = "turned away (challenge page)"
LOGIN = "login wall"
ROBOTS = "robots.txt disallows"
TIMEOUT_L = "timeout"
ERROR = "error"
NOT_FOUND = "not found"


def classify(status: int, body: str) -> str:
    """Turn one HTTP response into an outcome label."""
    low = body[:200_000].lower()
    if status in (401, 403, 429):
        if any(m in low for m in CHALLENGE_MARKERS):
            return CHALLENGE
        return TURNED_AWAY
    if status in (404, 410):
        return NOT_FOUND
    if status >= 500:
        if any(m in low for m in CHALLENGE_MARKERS):
            return CHALLENGE
        return ERROR
    if 200 <= status < 300:
        if any(m in low for m in ("cf-chl", "just a moment...", "_incapsula_resource")):
            return CHALLENGE
        if any(re.search(p, low) for p in LOGIN_MARKERS) and len(low) < 20_000:
            return LOGIN
        return LOADS
    return ERROR


def robots_allows(url: str, session: requests.Session) -> tuple[bool, str]:
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        r = session.get(robots_url, timeout=15)
    except requests.RequestException as e:
        return True, f"robots.txt not reachable ({type(e).__name__}); treated as allowed"
    if r.status_code >= 400:
        return True, f"robots.txt status {r.status_code}; treated as allowed"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(r.text.splitlines())
    ok = rp.can_fetch(USER_AGENT, url)
    return ok, "robots.txt allows" if ok else "robots.txt disallows this page"


def fetch(url: str, session: requests.Session) -> dict:
    attempts = 0
    wait = 2
    last_err = ""
    while attempts < RETRIES:
        attempts += 1
        started = time.monotonic()
        try:
            r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        except requests.Timeout:
            last_err = "timeout"
        except requests.RequestException as e:
            last_err = f"{type(e).__name__}: {str(e)[:160]}"
        else:
            outcome = classify(r.status_code, r.text)
            result = {
                "status": r.status_code,
                "outcome": outcome,
                "final_url": r.url,
                "bytes": len(r.content),
                "seconds": round(time.monotonic() - started, 2),
                "attempts": attempts,
                "server": r.headers.get("server", ""),
            }
            # COL 15: retry only server errors, never a block.
            if outcome == ERROR and r.status_code >= 500 and attempts < RETRIES:
                time.sleep(wait)
                wait *= 2
                continue
            return result
        if attempts < RETRIES:
            time.sleep(wait)
            wait *= 2
    return {
        "status": None,
        "outcome": TIMEOUT_L if last_err == "timeout" else ERROR,
        "error": last_err,
        "attempts": attempts,
    }


def run() -> dict:
    with open(SAMPLE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    last_hit: dict[str, float] = {}
    results = []
    for row in rows:
        url = row["scrape_url"]
        host = urlparse(url).netloc
        gap = time.monotonic() - last_hit.get(host, 0)
        if gap < PACE:
            time.sleep(PACE - gap)
        allowed, robots_note = robots_allows(url, session)
        if allowed:
            res = fetch(url, session)
        else:
            res = {"status": None, "outcome": ROBOTS, "attempts": 0}
        last_hit[host] = time.monotonic()
        res.update(
            {
                "entity_id": row["entity_id"],
                "entity_name": row["entity_name"],
                "url": url,
                "listing_type": row["listing_type"],
                "robots": robots_note,
            }
        )
        results.append(res)
        print(f"{row['entity_id']} {res['outcome']:<30} {res.get('status')} {url}", flush=True)

    counts: dict[str, int] = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    report = {
        "run_at": now_utc().isoformat(),
        "run_date_et": today_et(),
        "user_agent": USER_AGENT,
        "sample_size": len(results),
        "counts": counts,
        "results": results,
    }
    write_json(DATA / "reach" / f"{report['run_date_et']}.json", report)
    write_json(DATA / "reach" / "latest.json", report)
    return report


if __name__ == "__main__":
    rep = run()
    print("SUMMARY", rep["counts"])
    sys.exit(0)
