"""Builds the published site in public/.

- public/index.html: the page, with the run status embedded so it always shows
  the last run even if the bid file fails to load (WEB 20, HLT 5).
- public/bids.json: open bids plus bids closed in the last 14 days, trimmed to
  the fields the page shows. GitHub Pages serves it compressed.
"""
import datetime as dt
import json

from engine.common import DATA, ROOT, now_utc, read_json, today_et, write_json
from engine.health import source_status

TEMPLATE = ROOT / "site" / "index.template.html"
OUT = ROOT / "public" / "index.html"
RECENT_CLOSED_DAYS = 14
PAGE_FIELDS = ("bid_id", "title", "agency", "state", "county", "city", "solicitation_number",
               "notice_type", "posted_date", "due_at", "status", "set_aside", "is_new",
               "naics", "sources", "source_links", "first_seen", "description_text")


def page_bids(bids: list, today: dt.date) -> list:
    cutoff = (today - dt.timedelta(days=RECENT_CLOSED_DAYS)).isoformat()
    keep = [b for b in bids if b.get("status") == "open" or (b.get("due_at") or "")[:10] >= cutoff]
    return [{k: b.get(k) for k in PAGE_FIELDS if b.get(k) not in (None, "", [])} for b in keep]


def build_status(bids: list) -> dict:
    latest = read_json(DATA / "runs" / "latest.json", {}) or {}
    reach = read_json(DATA / "reach" / "latest.json", {}) or {}
    return {
        "built_at": now_utc().isoformat(),
        "last_run": {k: latest.get(k) for k in ("start", "end", "trigger", "result", "run_id")},
        "total_bids": len(bids),
        "open_bids": sum(1 for b in bids if b.get("status") == "open"),
        "new_today": sum(1 for b in bids if b.get("is_new")),
        "sources": source_status(),
        "reach_test": {
            "run_at": reach.get("run_at"),
            "counts": reach.get("counts", {}),
            "results": [
                {k: r.get(k) for k in ("entity_name", "url", "outcome", "status", "listing_type")}
                for r in reach.get("results", [])
            ],
        },
    }


def main(out=None, status_path=None) -> None:
    out = out or OUT
    bids = read_json(DATA / "index" / "bids.json", []) or []
    status = build_status(bids)
    write_json(status_path or (DATA / "status.json"), status)
    shown = page_bids(bids, dt.date.fromisoformat(today_et()))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out.parent / "bids.json", shown, compact=True)
    payload = json.dumps({"status": status, "bids_file": "bids.json"}, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    out.write_text(html, encoding="utf-8")
    print(f"built {out} with {len(shown)} of {len(bids)} bids on the page")


if __name__ == "__main__":
    main()
