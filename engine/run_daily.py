"""The daily job: run every enabled collector, the reach test, health, and the page build.

COL 2: each collector runs in its own process, so one failure cannot stop or
corrupt the others. COL 3: each has a time limit. HLT 1: every run writes a
run record to data/runs/<date>.json.
"""
import json
import os
import subprocess
import sys
import time

from engine.common import DATA, ROOT, load_sources, now_utc, read_json, today_et, write_json

COLLECTOR_TIME_LIMIT = int(os.environ.get("COLLECTOR_TIME_LIMIT", "1800"))


def run_collector(src: dict, run_date: str) -> dict:
    """Run one collector as `python -m collectors.<name>`; it writes data/raw/<date>/<source_id>.json."""
    started = now_utc()
    t0 = time.monotonic()
    out_file = DATA / "raw" / run_date / f"{src['source_id']}.json"
    rec = {"source_id": src["source_id"], "start": started.isoformat()}
    try:
        p = subprocess.run(
            [sys.executable, "-m", f"collectors.{src['collector']}", src["source_id"], str(out_file)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=COLLECTOR_TIME_LIMIT,
        )
        rec["exit_code"] = p.returncode
        rec["log_tail"] = (p.stdout + p.stderr)[-2000:]
        rec["result"] = "ok" if p.returncode == 0 else "error"
    except subprocess.TimeoutExpired:
        rec["result"] = "timeout"
    rec["end"] = now_utc().isoformat()
    rec["seconds"] = round(time.monotonic() - t0, 1)
    out = read_json(out_file, {}) or {}
    rec["items_seen"] = len(out.get("items", []))
    rec["errors"] = out.get("errors", [])
    rec["blocked"] = out.get("blocked", False)
    return rec


def run_store() -> dict:
    """Cleanup and merge (engine/store.py) in its own process."""
    p = subprocess.run([sys.executable, "-m", "engine.store"], cwd=ROOT, capture_output=True, text=True, timeout=1800)
    print(p.stdout[-2000:], p.stderr[-2000:])
    line = next((l for l in p.stdout.splitlines() if l.startswith("STORE ")), "")
    return {"result": "ok" if p.returncode == 0 else "error",
            "summary": json.loads(line[6:]) if line else {}}


def run_reach_test() -> dict:
    p = subprocess.run(
        [sys.executable, "-m", "engine.reach_test"], cwd=ROOT, capture_output=True, text=True, timeout=1800
    )
    print(p.stdout[-4000:], p.stderr[-2000:])
    rep = read_json(DATA / "reach" / "latest.json", {}) or {}
    return {"result": "ok" if p.returncode == 0 else "error", "counts": rep.get("counts", {})}


def main() -> int:
    run_date = today_et()
    trigger = os.environ.get("GITHUB_EVENT_NAME", "local")
    record = {
        "run_date_et": run_date,
        "start": now_utc().isoformat(),
        "trigger": trigger,
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "collectors": [],
    }
    for src in load_sources():
        if src["enabled"].strip().lower() != "yes":
            continue
        rec = run_collector(src, run_date)
        print(json.dumps({k: v for k, v in rec.items() if k != "log_tail"}))
        record["collectors"].append(rec)

    record["store"] = run_store()
    if os.environ.get("RUN_SAM_PROBE") == "1":
        subprocess.run([sys.executable, "-m", "engine.sam_probe"], cwd=ROOT, timeout=300)
    record["reach_test"] = run_reach_test()
    record["end"] = now_utc().isoformat()
    record["result"] = (
        "ok" if all(c["result"] == "ok" for c in record["collectors"]) and record["store"]["result"] == "ok"
        else "partial"
    )
    # One record per run; a second run on the same day keeps both.
    runs_dir = DATA / "runs"
    name = f"{run_date}_{trigger}_{record['run_id'] or 'local'}.json"
    write_json(runs_dir / name, record)
    write_json(runs_dir / "latest.json", record)
    print("RUN RESULT", record["result"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
