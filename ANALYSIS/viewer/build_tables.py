"""
build_tables.py — Rend les CSV de RESULTS/ lisibles par RESULTS/viewer/tables.html.

Un navigateur qui ouvre une page locale (file://) ne peut pas lister ni lire un dossier :
ce script recopie donc le texte de chaque RESULTS/**/*.csv dans
  RESULTS/viewer/data/tables.js
et copie la page ANALYSIS/viewer/tables.html dans RESULTS/viewer/.
Rapide (quelques secondes). Aussi lancé à la fin de build_viewer.py.

Usage : python ANALYSIS/viewer/build_tables.py   puis ouvrir RESULTS/viewer/tables.html
"""

import json
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = ROOT / "RESULTS"
OUT = RESULTS / "viewer"


def main():
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "tables.html", OUT / "tables.html")
    tables = []
    for p in sorted(RESULTS.rglob("*.csv")):
        if OUT in p.parents:
            continue
        tables.append({
            "name": p.relative_to(RESULTS).as_posix(),
            "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)),
            "text": p.read_text(encoding="utf-8-sig"),
        })
        print(f"  {tables[-1]['name']}")
    (OUT / "data" / "tables.js").write_text(
        "window.RESULTS_TABLES=" + json.dumps(tables, ensure_ascii=False) + ";", encoding="utf-8")
    print(f"{len(tables)} CSV -> ouvrir {OUT / 'tables.html'}")


if __name__ == "__main__":
    main()
