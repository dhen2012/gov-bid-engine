"""SAM.gov Contract Opportunities collector (PRD 7.4, phase 1).

Reads the official Get Opportunities Public API with the key in the
SAM_GOV_API_KEY secret. The key is sent only as a request parameter and is
scrubbed from every message this module prints or saves (CFG 5, NFR 6).

Usage: python -m collectors.sam_gov <source_id> <out_file>
"""
import datetime as dt
import os
import sys
import time

import requests

from engine.common import ET, USER_AGENT, now_utc, write_json

API = "https://api.sam.gov/opportunities/v2/search"
PAGE = 1000
LOOKBACK_DAYS = int(os.environ.get("SAM_LOOKBACK_DAYS", "2"))
# Without a role a key may get only 10 requests a day (Entity API page; not yet confirmed for this API).
MAX_REQUESTS = int(os.environ.get("SAM_MAX_REQUESTS", "8"))

NOTICE_TYPES = {
    "o": "solicitation",
    "k": "combined synopsis/solicitation",
    "p": "presolicitation",
    "r": "sources sought",
    "s": "special notice",
    "a": "award",
    "u": "justification",
    "g": "sale of surplus property",
    "i": "intent to bundle",
}


def scrub(text: str, key: str) -> str:
    return text.replace(key, "***") if key else text


def public_link(notice_id: str) -> str:
    # uiLink needs a contracting officer role (PRD 7.4); this is the public view.
    return f"https://sam.gov/opp/{notice_id}/view"


def due_of(rec: dict):
    # The API docs spell this field two ways.
    return rec.get("responseDeadLine") or rec.get("reponseDeadLine")


def place(rec: dict) -> tuple[str, str, str]:
    pop = rec.get("placeOfPerformance") or {}
    state = ((pop.get("state") or {}).get("code") or "").upper()
    city = (pop.get("city") or {}).get("name") or ""
    county = ""
    if not state:
        office = rec.get("officeAddress") or {}
        state = (office.get("state") or "").upper()
        city = city or office.get("city") or ""
    return state, county, city


def to_standard(rec: dict, source_id: str, collected_at: str) -> dict:
    state, county, city = place(rec)
    nid = rec.get("noticeId", "")
    agency = rec.get("fullParentPathName") or rec.get("department") or rec.get("organizationName") or ""
    links = rec.get("resourceLinks") or []
    return {
        "source_id": source_id,
        "source_record_id": nid,
        "title": (rec.get("title") or "").strip(),
        "agency_name_raw": agency,
        "state": state or "US",
        "county": county,
        "city": city,
        "solicitation_number": rec.get("solicitationNumber") or "",
        "notice_type": (rec.get("type") or "").strip().lower(),
        "posted_date": rec.get("postedDate") or "",
        "due_date": due_of(rec) or "",
        "listing_url": public_link(nid),
        "documents_url": links[0] if links else "",
        "documents_access": "public" if links else "unknown",
        "naics_raw": rec.get("naicsCode") or "",
        "other_codes_raw": rec.get("classificationCode") or "",
        "set_aside": rec.get("typeOfSetAsideDescription") or rec.get("typeOfSetAside") or "",
        "description_text": "",
        "active": rec.get("active"),
        "collected_at": collected_at,
    }


def main(source_id: str, out_file: str) -> int:
    key = os.environ.get("SAM_GOV_API_KEY", "")
    collected_at = now_utc().isoformat()
    result = {"source_id": source_id, "collected_at": collected_at, "items": [], "errors": [],
              "blocked": False, "requests": 0, "rate_limit": {}}
    if not key:
        result["errors"].append("SAM_GOV_API_KEY secret is not set")
        write_json(__import__("pathlib").Path(out_file), result)
        print("no key; nothing collected")
        return 1

    today = dt.datetime.now(dt.timezone.utc).astimezone(ET).date()
    start = today - dt.timedelta(days=LOOKBACK_DAYS)
    params = {
        "api_key": key,
        "postedFrom": start.strftime("%m/%d/%Y"),
        "postedTo": today.strftime("%m/%d/%Y"),
        "limit": PAGE,
        "offset": 0,
    }
    result["window"] = {"postedFrom": params["postedFrom"], "postedTo": params["postedTo"]}
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    total = None
    while True:
        if result["requests"] >= MAX_REQUESTS:
            result["errors"].append(f"stopped at the request cap of {MAX_REQUESTS}")
            break
        wait, resp = 2, None
        for attempt in range(3):
            if result["requests"] >= MAX_REQUESTS:
                break
            try:
                resp = session.get(API, params=params, timeout=60)
            except requests.RequestException as e:
                result["errors"].append(scrub(f"{type(e).__name__}: {e}", key)[:300])
                resp = None
            result["requests"] += 1
            if resp is not None and resp.status_code < 500:
                break
            time.sleep(wait)
            wait *= 2
        if resp is None:
            break
        for h in ("X-RateLimit-Limit", "X-RateLimit-Remaining"):
            if h in resp.headers:
                result["rate_limit"][h] = resp.headers[h]
        if resp.status_code == 429:
            result["errors"].append("429 rate limit reached")
            break
        if resp.status_code in (401, 403):
            result["errors"].append(f"{resp.status_code}: {scrub(resp.text, key)[:300]}")
            result["blocked"] = resp.status_code == 403
            break
        if resp.status_code != 200:
            result["errors"].append(f"status {resp.status_code}: {scrub(resp.text, key)[:300]}")
            break
        try:
            body = resp.json()
        except ValueError:
            result["errors"].append(f"status 200 but the reply was not JSON: {scrub(resp.text, key)[:200]}")
            break
        total = body.get("totalRecords", 0)
        batch = body.get("opportunitiesData") or []
        result["items"].extend(to_standard(r, source_id, collected_at) for r in batch)
        params["offset"] += PAGE
        if not batch or params["offset"] >= total:
            break
        time.sleep(1)
    result["total_records_reported"] = total
    write_json(__import__("pathlib").Path(out_file), result)
    print(f"sam_gov: {len(result['items'])} items of {total} reported, {result['requests']} requests, "
          f"rate limit {result['rate_limit']}, errors {len(result['errors'])}")
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
