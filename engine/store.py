"""Cleanup, merge and storage (PRD 9 and 11), phase 1 scope.

Reads every collector output in data/raw/<run_date>/, turns each item into a
bid record, merges it into data/index/bids.json (all history kept, STO 3),
logs field changes to data/index/changes.json, and writes the day's new and
changed bids to data/daily/<run_date>.json (STO 1).

Phase 1 merge key is the source's own record ID (a SAM noticeId). Matching the
same bid across different sources starts in phase 2, when a second source exists.
"""
import csv
import datetime as dt
import gzip
import hashlib
import json
import re
import sys

from engine.common import CONFIG, DATA, ET, now_utc, read_json, today_et, write_json

ARCHIVE_AFTER_DAYS = 30
TRACKED_FIELDS = ("title", "due_at", "status", "notice_type", "solicitation_number", "set_aside")

NOTICE_MAP = [
    (r"combined synopsis", "solicitation"),
    (r"^solicitation", "solicitation"),
    (r"presolicitation", "presolicitation"),
    (r"sources sought", "sources sought"),
    (r"award", "award"),
    (r"special notice", "special notice"),
    (r"\brfp\b|request for proposal", "RFP"),
    (r"\brfq\b|request for quot", "RFQ"),
    (r"\bifb\b|invitation for bid", "IFB"),
    (r"\bitb\b|invitation to bid", "ITB"),
]


def normalize_notice_type(raw: str) -> str:
    low = (raw or "").strip().lower()
    if not low:
        return "other"
    for pattern, label in NOTICE_MAP:
        if re.search(pattern, low):
            return label
    return "other"


def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def make_bid_id(source_id: str, record_id: str, fallback: str) -> str:
    key = f"{source_id}|{record_id or fallback}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def make_agency_id(name: str, state: str) -> str:
    norm = re.sub(r"[^a-z0-9 ]", "", normalize_space(name).lower())
    return hashlib.sha1(f"{state}|{norm}".encode("utf-8")).hexdigest()[:12]


def parse_due(raw: str):
    """Returns an ISO string. Date only values stay date only (PRD 11.2)."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}(?::\d{2})?)([+-]\d{2}):?(\d{2})$", raw)
    if m:
        return f"{m.group(1)}T{m.group(2)}{m.group(3)}:{m.group(4)}"
    return raw


def status_of(notice_type: str, due_at: str, active, today: dt.date) -> str:
    if notice_type == "award":
        return "awarded"
    if due_at:
        try:
            due_day = dt.date.fromisoformat(due_at[:10])
            if due_day < today:
                return "closed"
        except ValueError:
            pass
    if isinstance(active, str) and active.strip().lower() == "no":
        return "closed"
    return "open"


def load_naics_names() -> dict:
    path = CONFIG / "naics_2022.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["code"]: r["title"] for r in csv.DictReader(f)}


def naics_codes(raw) -> list[str]:
    if isinstance(raw, list):
        vals = raw
    else:
        vals = re.split(r"[,;\s]+", str(raw or ""))
    return [v for v in vals if re.fullmatch(r"\d{2,6}", v)]


def to_bid(item: dict, source_name: str, names: dict, today: dt.date) -> dict:
    notice = normalize_notice_type(item.get("notice_type", ""))
    due = parse_due(item.get("due_date", ""))
    codes = naics_codes(item.get("naics_raw"))
    state = (item.get("state") or "").upper()
    agency = normalize_space(item.get("agency_name_raw", ""))
    return {
        "bid_id": make_bid_id(item["source_id"], item.get("source_record_id", ""), item.get("listing_url", "")),
        "title": normalize_space(item.get("title", "")),
        "agency": agency,
        "agency_id": make_agency_id(agency, state),
        "state": state,
        "county": item.get("county", ""),
        "city": normalize_space(item.get("city", "")),
        "solicitation_number": normalize_space(item.get("solicitation_number", "")),
        "notice_type": notice,
        "notice_type_raw": item.get("notice_type", ""),
        "posted_date": (item.get("posted_date") or "")[:10],
        "due_at": due,
        "status": status_of(notice, due, item.get("active"), today),
        "set_aside": item.get("set_aside", ""),
        "description_text": normalize_space(item.get("description_text", ""))[:600],
        "naics": [
            {"code": c, "name": names.get(c, ""), "origin": "from source", "confidence": "high"} for c in codes
        ],
        "sources": [source_name],
        "source_links": [
            {
                "source_id": item["source_id"],
                "source_record_id": item.get("source_record_id", ""),
                "listing_url": item.get("listing_url", ""),
                "documents_url": item.get("documents_url", ""),
                "documents_access": item.get("documents_access", "unknown"),
            }
        ],
        "match_quality": "single source",
    }


def merge(index: dict, bid: dict, now: str, run_date: str, changes: list) -> str:
    """Returns 'new', 'changed' or 'same'."""
    old = index.get(bid["bid_id"])
    if old is None:
        bid["first_seen"] = now
        bid["first_seen_date"] = run_date
        bid["last_seen"] = now
        index[bid["bid_id"]] = bid
        return "new"
    kind = "same"
    for f in TRACKED_FIELDS:
        if bid.get(f) and bid.get(f) != old.get(f):
            changes.append({"bid_id": bid["bid_id"], "changed_at": now, "field": f,
                            "old_value": old.get(f), "new_value": bid.get(f)})
            kind = "changed"
    keep = {k: old[k] for k in ("first_seen", "first_seen_date") if k in old}
    old.update(bid)
    old.update(keep)
    old["last_seen"] = now
    return kind


def refresh_status(index: dict, today: dt.date) -> None:
    """Bids not seen today still close when their due date passes."""
    for b in index.values():
        if b.get("status") == "open":
            b["status"] = status_of(b.get("notice_type", ""), b.get("due_at", ""), None, today)


def archive_old(index: dict, today: dt.date) -> int:
    """STO 3: closed bids are never deleted. Bids that are not open and were last
    seen more than ARCHIVE_AFTER_DAYS ago move from the working index into
    data/history/<YYYY-MM of first seen>.jsonl.gz, one JSON line per bid."""
    cutoff = (today - dt.timedelta(days=ARCHIVE_AFTER_DAYS)).isoformat()
    moving = [b for b in index.values()
              if b.get("status") != "open" and (b.get("last_seen") or "")[:10] < cutoff]
    by_month: dict[str, list] = {}
    for b in moving:
        by_month.setdefault((b.get("first_seen_date") or "unknown")[:7], []).append(b)
    for month, rows in by_month.items():
        path = DATA / "history" / f"{month}.jsonl.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "at", encoding="utf-8") as f:
            for b in rows:
                f.write(json.dumps(b, separators=(",", ":"), sort_keys=True) + "\n")
    for b in moving:
        del index[b["bid_id"]]
    return len(moving)


def main(run_date: str | None = None) -> dict:
    run_date = run_date or today_et()
    today = dt.date.fromisoformat(run_date)
    now = now_utc().isoformat()
    names = load_naics_names()
    sources = {}
    with open(CONFIG / "sources.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sources[r["source_id"]] = r["name"]

    index = {b["bid_id"]: b for b in (read_json(DATA / "index" / "bids.json", []) or [])}
    changes_all = read_json(DATA / "index" / "changes.json", []) or []
    changes: list = []
    counts = {}
    daily = []
    raw_dir = DATA / "raw" / run_date
    for f in sorted(raw_dir.glob("*.json")) if raw_dir.exists() else []:
        out = json.loads(f.read_text(encoding="utf-8"))
        sid = out.get("source_id", f.stem)
        c = {"seen": 0, "new": 0, "changed": 0}
        for item in out.get("items", []):
            bid = to_bid(item, sources.get(sid, sid), names, today)
            kind = merge(index, bid, now, run_date, changes)
            c["seen"] += 1
            if kind != "same":
                c[kind] += 1
                daily.append(index[bid["bid_id"]])
        counts[sid] = c

    refresh_status(index, today)
    for b in index.values():
        b["is_new"] = b.get("first_seen_date") == run_date

    archived = archive_old(index, today)
    bids = sorted(index.values(), key=lambda b: (b.get("posted_date", ""), b["bid_id"]), reverse=True)
    write_json(DATA / "index" / "bids.json", bids, compact=True)
    write_json(DATA / "index" / "changes.json", changes_all + changes, compact=True)
    write_json(DATA / "daily" / f"{run_date}.json", {"run_date": run_date, "counts": counts, "bids": daily})
    summary = {"run_date": run_date, "counts": counts, "total": len(bids), "changes": len(changes),
               "archived": archived}
    print("STORE", json.dumps(summary))
    return summary


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
