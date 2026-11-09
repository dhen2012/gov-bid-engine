"""Shared helpers: paths, the honest user agent, time, and the sources table."""
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"

# COL 14: an honest user agent that names the engine.
USER_AGENT = (
    "GovBidEngine/0.1 (public government bid collector; "
    "+https://github.com/dhen2012/gov-bid-engine)"
)

from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def today_et() -> str:
    """Run date in Eastern time, used for daily file names."""
    return dt.datetime.now(dt.timezone.utc).astimezone(ET).date().isoformat()


def load_sources() -> list[dict]:
    with open(CONFIG / "sources.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
