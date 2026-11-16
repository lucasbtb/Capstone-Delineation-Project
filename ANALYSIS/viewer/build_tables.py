"""
build_tables.py — Makes the CSVs of the project readable by RESULTS/viewer/tables.html.

A browser opening a local page (file://) cannot list or read a folder: this script therefore copies
the text of every RESULTS/**/*.csv and DATA/DELINEATION_CLEAN/*.csv (delineations) into
  RESULTS/viewer/data/tables.js
and copies the page ANALYSIS/viewer/tables.html into RESULTS/viewer/.
Fast (a few seconds). Also run at the end of build_viewer.py.

Usage: python ANALYSIS/viewer/build_tables.py   then open RESULTS/viewer/tables.html
"""

import json
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = ROOT / "RESULTS"
CLEAN = ROOT / "DATA" / "DELINEATION_CLEAN"
OUT = RESULTS / "viewer"


def main():
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "tables.html", OUT / "tables.html")
    tables = []
    sources = sorted(CLEAN.glob("*.csv")) + sorted(RESULTS.rglob("*.csv"))
    for p in sources:
        if OUT in p.parents:
            continue
        tables.append({
            "name": p.relative_to(ROOT).as_posix(),
            "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)),
            "text": p.read_text(encoding="utf-8-sig"),
        })
        print(f"  {tables[-1]['name']}")
    (OUT / "data" / "tables.js").write_text(
        "window.RESULTS_TABLES=" + json.dumps(tables, ensure_ascii=False) + ";", encoding="utf-8")
    print(f"{len(tables)} CSV -> open {OUT / 'tables.html'}")


if __name__ == "__main__":
    main()
