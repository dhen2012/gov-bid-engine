import json

from collectors import sam_gov
from engine import store
from engine.common import ROOT

FIX = ROOT / "tests" / "fixtures" / "sam_gov" / "search_response_doc_shape.json"


def sam_items():
    body = json.loads(FIX.read_text())
    return [sam_gov.to_standard(r, "sam_gov", "2026-11-08T03:40:00+00:00") for r in body["opportunitiesData"]]


def test_sam_standard_shape():
    a, b = sam_items()
    assert a["listing_url"] == "https://sam.gov/opp/abc123def456/view"
    assert a["state"] == "SC" and a["city"] == "Charleston"
    assert a["due_date"] == "2026-11-21T14:00:00-0500"
    assert b["due_date"] == "2026-11-01"  # the misspelled field name is read too
    assert b["state"] == "GA"  # falls back to the office address
    for f in ("source_id", "title", "agency_name_raw", "state", "listing_url", "documents_access", "collected_at"):
        assert a[f]


def test_key_is_scrubbed():
    assert sam_gov.scrub("url?api_key=SECRET123&x=1", "SECRET123") == "url?api_key=***&x=1"


def test_store_merge_new_then_changed(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    raw = tmp_path / "raw" / "2026-11-08"
    raw.mkdir(parents=True)
    (raw / "sam_gov.json").write_text(json.dumps({"source_id": "sam_gov", "items": sam_items()}))
    s1 = store.main("2026-11-08")
    assert s1["counts"]["sam_gov"] == {"seen": 2, "new": 2, "changed": 0}
    bids = json.loads((tmp_path / "index" / "bids.json").read_text())
    by_title = {b["title"]: b for b in bids}
    web = by_title["Website Redesign and Hosting Services"]
    assert web["notice_type"] == "solicitation"
    assert web["due_at"] == "2026-11-21T14:00:00-05:00"
    assert web["status"] == "open" and web["is_new"]
    assert web["naics"][0]["code"] == "541511" and web["naics"][0]["origin"] == "from source"
    assert by_title["Sources Sought: Janitorial"]["status"] == "closed"

    # Next day: the due date moves. Same bid, logged as a change, no longer new.
    items = sam_items()
    items[0]["due_date"] = "2026-11-25T14:00:00-0500"
    raw2 = tmp_path / "raw" / "2026-11-09"
    raw2.mkdir(parents=True)
    (raw2 / "sam_gov.json").write_text(json.dumps({"source_id": "sam_gov", "items": items}))
    s2 = store.main("2026-11-09")
    assert s2["counts"]["sam_gov"]["new"] == 0 and s2["counts"]["sam_gov"]["changed"] == 1
    changes = json.loads((tmp_path / "index" / "changes.json").read_text())
    assert changes[-1]["field"] == "due_at"
    bids = json.loads((tmp_path / "index" / "bids.json").read_text())
    assert len(bids) == 2 and not any(b["is_new"] for b in bids)


def test_archive_moves_old_closed_bids(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    index = {"x": {"bid_id": "x", "status": "closed", "last_seen": "2026-09-01T00:00:00", "first_seen_date": "2026-08-20"},
             "y": {"bid_id": "y", "status": "open", "last_seen": "2026-09-01T00:00:00"}}
    import datetime as dt, gzip
    assert store.archive_old(index, dt.date(2026, 11, 8)) == 1
    assert list(index) == ["y"]
    with gzip.open(tmp_path / "history" / "2026-08.jsonl.gz", "rt") as f:
        assert json.loads(f.readline())["bid_id"] == "x"


def test_notice_types():
    assert store.normalize_notice_type("Award Notice") == "award"
    assert store.normalize_notice_type("Presolicitation") == "presolicitation"
    assert store.normalize_notice_type("Request for Quotation") == "RFQ"
    assert store.normalize_notice_type("") == "other"


class FakeResp:
    def __init__(self, status, body=None, text=""):
        self.status_code, self._body, self.text, self.headers = status, body, text, {}

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


def run_fake(monkeypatch, tmp_path, replies, cap=8):
    calls = []

    class FakeSession:
        headers = {}

        def get(self, url, params=None, timeout=None):
            calls.append(dict(params or {}))
            return replies(len(calls))

    monkeypatch.setattr(sam_gov.requests, "Session", FakeSession)
    monkeypatch.setattr(sam_gov.time, "sleep", lambda s: None)
    monkeypatch.setattr(sam_gov, "MAX_REQUESTS", cap)
    monkeypatch.setenv("SAM_GOV_API_KEY", "SECRETKEY")
    out = tmp_path / "out.json"
    sam_gov.main("sam_gov", str(out))
    return calls, json.loads(out.read_text())


def test_cap_holds_even_during_retries(monkeypatch, tmp_path):
    calls, res = run_fake(monkeypatch, tmp_path, lambda n: FakeResp(503, text="down"), cap=2)
    assert len(calls) == 2 and res["requests"] == 2


def test_non_json_reply_keeps_earlier_pages(monkeypatch, tmp_path):
    page = {"totalRecords": 2000, "opportunitiesData": json.loads(FIX.read_text())["opportunitiesData"]}
    calls, res = run_fake(monkeypatch, tmp_path,
                          lambda n: FakeResp(200, page) if n == 1 else FakeResp(200, None, "<html>maintenance SECRETKEY</html>"))
    assert len(res["items"]) == 2
    assert any("not JSON" in e for e in res["errors"])
    assert "SECRETKEY" not in json.dumps(res)
