"""Phase 1 probe, run from GitHub Actions: robots.txt for sam.gov and api.sam.gov,
and whether the public extract file ContractOpportunitiesFullCSV.csv answers
without a login (headers only, the file is not downloaded). Writes data/probes/sam_gov.json."""
import requests

from engine.common import DATA, USER_AGENT, now_utc, write_json

EXTRACT = ("https://sam.gov/api/prod/fileextractservices/v1/api/download/"
           "Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv?privacy=Public")


def main():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    out = {"run_at": now_utc().isoformat()}
    for name, url in (("sam_robots", "https://sam.gov/robots.txt"), ("api_robots", "https://api.sam.gov/robots.txt")):
        try:
            r = s.get(url, timeout=30)
            out[name] = {"status": r.status_code, "text": r.text[:4000]}
        except requests.RequestException as e:
            out[name] = {"error": type(e).__name__}
    try:
        r = s.get(EXTRACT, timeout=60, stream=True, allow_redirects=True)
        out["extract"] = {"status": r.status_code, "final_url": r.url.split("?")[0],
                          "content_type": r.headers.get("content-type"),
                          "content_length": r.headers.get("content-length"),
                          "last_modified": r.headers.get("last-modified"),
                          "first_line": next(r.iter_lines(), b"")[:600].decode("utf-8", "replace")}
        r.close()
    except requests.RequestException as e:
        out["extract"] = {"error": type(e).__name__}
    write_json(DATA / "probes" / "sam_gov.json", out)
    print({k: (v.get("status") if isinstance(v, dict) else v) for k, v in out.items()})


if __name__ == "__main__":
    main()
