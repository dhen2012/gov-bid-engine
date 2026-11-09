"""Builds config/reach_test_sample.csv: 20 SC bid pages for the BLK 9 reach test.

Deterministic: only Opus checked rows with a scrape URL (verdict Confirmed or
Corrected), one page per host, spread across listing types, picked in order of
a SHA1 hash of the entity ID so the same 20 come out every time.
"""
import csv
import hashlib
from urllib.parse import urlparse

from engine.common import CONFIG

QUOTA = {"html list": 10, "pdf links": 5, "news posts": 2, "iframe or embedded portal": 3}


def main():
    src = CONFIG / "sc_verified_bid_pages.csv"
    rows = list(csv.DictReader(open(src, newline="", encoding="utf-8")))
    rows = [
        r for r in rows
        if r["verdict"] in ("Confirmed", "Corrected") and r["scrape_url"].startswith("http")
    ]
    rows.sort(key=lambda r: hashlib.sha1(r["entity_id"].encode()).hexdigest())
    seen_hosts, picked = set(), []
    for ltype, n in QUOTA.items():
        got = 0
        for r in rows:
            host = urlparse(r["scrape_url"]).netloc.lower()
            if r["listing_type"] == ltype and host not in seen_hosts and got < n:
                picked.append(r)
                seen_hosts.add(host)
                got += 1
    # Fill any shortfall from the remaining rows.
    for r in rows:
        if len(picked) >= 20:
            break
        host = urlparse(r["scrape_url"]).netloc.lower()
        if host not in seen_hosts:
            picked.append(r)
            seen_hosts.add(host)
    cols = ["entity_id", "entity_name", "scrape_url", "listing_type", "notes"]
    with open(CONFIG / "reach_test_sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(picked[:20])
    print(f"wrote {len(picked[:20])} rows")


if __name__ == "__main__":
    main()
