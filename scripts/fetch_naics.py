"""Downloads the official 2022 NAICS code list from the Census Bureau and writes
config/naics_2022.csv (code, title). Runs in GitHub Actions only when the file
is missing, because this work machine cannot reach census.gov."""
import csv
import io
import sys

import openpyxl
import requests

from engine.common import CONFIG, USER_AGENT

URL = "https://www.census.gov/naics/2022NAICS/2-6%20digit_2022_Codes.xlsx"


def main() -> int:
    out = CONFIG / "naics_2022.csv"
    if out.exists():
        print("naics_2022.csv already present")
        return 0
    r = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=60)
    print("census status", r.status_code)
    if r.status_code != 200:
        return 0  # the engine runs without names; the page shows codes only
    wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        code, title = (row[1] if len(row) > 1 else None), (row[2] if len(row) > 2 else None)
        code = str(code).strip() if code is not None else ""
        if code.isdigit() and 2 <= len(code) <= 6 and title:
            rows.append((code, str(title).strip().rstrip("T").strip()))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "title"])
        w.writerows(rows)
    print(f"wrote {len(rows)} NAICS codes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
