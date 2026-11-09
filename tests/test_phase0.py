import csv
import json

from engine import reach_test as rt
from engine.common import CONFIG, ROOT


def test_classify_outcomes():
    assert rt.classify(200, "<html><body>Bids</body></html>") == rt.LOADS
    assert rt.classify(403, "Forbidden") == rt.TURNED_AWAY
    assert rt.classify(403, "<title>Just a moment...</title>") == rt.CHALLENGE
    assert rt.classify(503, "cf-chl challenge") == rt.CHALLENGE
    assert rt.classify(429, "slow down") == rt.TURNED_AWAY
    assert rt.classify(404, "gone") == rt.NOT_FOUND
    assert rt.classify(500, "oops") == rt.ERROR
    assert rt.classify(200, '<form><input type="password"></form>') == rt.LOGIN


def test_reach_sample_is_20_unique_hosts():
    rows = list(csv.DictReader(open(CONFIG / "reach_test_sample.csv", newline="", encoding="utf-8")))
    assert len(rows) == 20
    hosts = {r["scrape_url"].split("/")[2].lower() for r in rows}
    assert len(hosts) == 20


def test_sources_table_has_required_columns():
    rows = list(csv.DictReader(open(CONFIG / "sources.csv", newline="", encoding="utf-8")))
    need = {"source_id", "name", "layer", "collector", "base_url", "states", "read_method",
            "channel", "wait_seconds", "pace_seconds", "enabled", "review_file", "notes"}
    assert need <= set(rows[0].keys())
    assert len({r["source_id"] for r in rows}) == len(rows)


def test_page_builds_self_contained(tmp_path, monkeypatch):
    from engine import build_page
    out = tmp_path / "index.html"
    monkeypatch.setattr(build_page, "OUT", out)
    build_page.main()
    html = out.read_text(encoding="utf-8")
    for tag in ("<!doctype html>", "<html", "<head>", "<body>", "</html>"):
        assert tag in html
    assert "/*__DATA__*/null" not in html
    assert 'name="robots" content="noindex' in html


def test_no_long_dashes_in_page_or_docs():
    bad = [chr(0x2014), chr(0x2013)]
    for p in [ROOT / "site" / "index.template.html", ROOT / "README.md", ROOT / "docs" / "decisions.md"]:
        text = p.read_text(encoding="utf-8")
        assert not any(b in text for b in bad), p
