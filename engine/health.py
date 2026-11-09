"""HLT 2 to HLT 4: per source health from the run history, for the status panel."""
from engine.common import DATA, load_sources, read_json

POSSIBLY_BROKEN = "possibly broken"
BLOCKED = "blocked"


def run_history(limit: int = 30) -> list[dict]:
    files = sorted(p for p in (DATA / "runs").glob("*.json") if p.name != "latest.json")
    runs = [read_json(p) for p in files[-limit:]]
    return [r for r in runs if r]


def source_status() -> list[dict]:
    runs = run_history()
    rows = []
    for src in load_sources():
        sid = src["source_id"]
        counts, results, blocked = [], [], False
        for r in runs:
            for c in r.get("collectors", []):
                if c["source_id"] == sid:
                    counts.append(c.get("items_seen", 0))
                    results.append(c.get("result"))
                    blocked = c.get("blocked", False)
        enabled = src["enabled"].strip().lower() == "yes"
        today = counts[-1] if counts else None
        prior = counts[-8:-1]
        avg7 = round(sum(prior) / len(prior), 1) if prior else None
        flag = ""
        if enabled and counts:
            if blocked:
                flag = BLOCKED
            elif results and results[-1] != "ok":
                flag = POSSIBLY_BROKEN
            elif len(counts) >= 2 and counts[-1] == 0 and counts[-2] == 0:
                flag = POSSIBLY_BROKEN
            elif avg7 and today is not None and today < 0.3 * avg7:
                flag = POSSIBLY_BROKEN
        rows.append(
            {
                "source_id": sid,
                "name": src["name"],
                "channel": src["channel"] if enabled else f"{src['channel']} (off until phase {src['phase']})",
                "enabled": enabled,
                "today": today,
                "avg7": avg7,
                "flag": flag,
            }
        )
    return rows
