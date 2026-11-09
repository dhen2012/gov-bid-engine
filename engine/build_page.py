"""Builds public/index.html: one self contained page (WEB 3) with the bid data and status inside it."""
import json

from engine.common import DATA, ROOT, now_utc, read_json, write_json
from engine.health import source_status

TEMPLATE = ROOT / "site" / "index.template.html"
OUT = ROOT / "public" / "index.html"


def main() -> None:
    bids = read_json(DATA / "index" / "bids.json", []) or []
    latest = read_json(DATA / "runs" / "latest.json", {}) or {}
    reach = read_json(DATA / "reach" / "latest.json", {}) or {}
    status = {
        "built_at": now_utc().isoformat(),
        "last_run": {
            "start": latest.get("start"),
            "end": latest.get("end"),
            "trigger": latest.get("trigger"),
            "result": latest.get("result"),
            "run_id": latest.get("run_id"),
        },
        "total_bids": len(bids),
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
    write_json(DATA / "status.json", status)
    payload = json.dumps({"bids": bids, "status": status}, separators=(",", ":"))
    # Keep "</" out of the inline script.
    payload = payload.replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"built {OUT} with {len(bids)} bids")


if __name__ == "__main__":
    main()
