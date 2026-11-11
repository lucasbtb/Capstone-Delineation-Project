"""
01_inventory.py — État des lieux des délinéations brutes (lecture seule).

Applique à chaque fichier de DATA/DELINEATION_DATA les 5 tests de checks.py :
  1. naming       nom conforme à naming.md, rater du nom = dossier
  2. extension    vrai .nii.gz
  3. labels       exactement les noyaux 1 à 9
  4. duplicate    plusieurs fichiers pour le même rater + scan (copie exacte ou contenu différent)
  5. orientation  grille 192x224x224 à 1 mm, header RAS, pas de retournement gauche-droite

Sorties :
  - un résumé dans le terminal ;
  - RESULTS/01_inventory.csv : une ligne par fichier, colonnes <test>_ok / <test>_detail,
    et 'errors' = liste lisible de toutes les erreurs du fichier.

Ne modifie aucun fichier de données.
Usage : python ANALYSIS/01_inventory.py
"""

import csv
from collections import Counter
from pathlib import Path

from checks import PROBLEMS, build_inventory

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "DATA" / "DELINEATION_DATA"
OUT = ROOT / "RESULTS" / "01_inventory.csv"

COLUMNS = (["group", "rater", "file", "scan", "errors", "all_ok"]
           + [c for p in PROBLEMS for c in (f"{p}_ok", f"{p}_detail")]
           + ["labels", "dice_vs_others", "dice_flipped_vs_others", "lr_flip_suspect", "content_hash"])


def write_csv(rows, path):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # -sig : accents lisibles dans Excel
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def summary(rows):
    n = len(rows)
    print(f"Fichiers : {n}  ({len({r['rater'] for r in rows})} raters avec au moins un fichier)\n")
    for k, p in enumerate(PROBLEMS, 1):
        ok = sum(1 for r in rows if r[f"{p}_ok"] is True)
        print(f"{k}. {p:12s} : {ok}/{n} OK")
        details = Counter(r[f"{p}_detail"] for r in rows if r[f"{p}_ok"] is not True)
        if p == "duplicate":  # regrouper par type de doublon, pas par fichier
            details = Counter(d.split(" de ")[0] for d in details.elements())
        for detail, c in details.most_common(8):
            print(f"     {c:3d}  {detail}")
        if len(details) > 8:
            print(f"     ...  {len(details) - 8} autres cas (voir le CSV)")
    flips = [r for r in rows if r["lr_flip_suspect"] is True]
    checked = sum(1 for r in rows if r["lr_flip_suspect"] != "")
    print(f"   gauche-droite retourné suspect : {len(flips)}/{checked} vérifiés")
    for r in flips:
        print(f"     {r['file']}  (Dice {r['dice_vs_others']} -> {r['dice_flipped_vs_others']} retourné)")
    print(f"\nTout OK : {sum(1 for r in rows if r['all_ok'])}/{n}")


if __name__ == "__main__":
    rows = build_inventory(DATA, verbose=True)
    write_csv(rows, OUT)
    summary(rows)
    print(f"Détail : {OUT.relative_to(ROOT)}")
