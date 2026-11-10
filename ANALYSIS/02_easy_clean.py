"""
02_easy_clean.py — Construit DATA/CLEAN_DELINEATION en corrigeant les problèmes 1 à 5.

Pour chaque fichier brut (tests de checks.py) :
  3. LABELS      pas exactement les noyaux 1 à 9 (ou illisible, IRM, vide) -> exclu
  5. ORIENTATION header non RAS -> réorienté en RAS (fix_orientation) ;
                 mauvaise grille (taille / voxel) ou masque retourné gauche-droite
                 suspect par rapport aux autres raters -> exclu
  1. NAMING      renommé au format final, sujet + session lus dans le nom mal écrit,
                 rater pris du dossier :  SUBC001_ses01_Rater1a_manual_seg.nii.gz
                 sujet / session illisible ou session hors 1-2 -> exclu
  4. DUPLICATE   plusieurs fichiers valides pour le même rater + scan :
                   copies exactes      -> une seule gardée (de préférence le vrai .nii.gz)
                   contenus différents -> tous exclus (impossible de savoir lequel est le bon)
  2. EXTENSION   écrit en vrai .nii.gz : .nii compressé, .nii.gz.gz / '(1).gz' / .zip
                 décompressés puis recompressés. Le contenu NIfTI reste identique octet pour octet
                 (sauf fichier réorienté, réécrit par nibabel).

Ensuite (avec --apply) : relance les 5 tests sur CLEAN_DELINEATION et vérifie
que chaque masque copié a les mêmes voxels que l'original (réorienté si besoin).

Ne modifie jamais DATA/DELINEATION_DATA.
Sorties : DATA/CLEAN_DELINEATION/Group N/Rater Nx/...   (vidé puis recréé, uniquement avec --apply)
          RESULTS/02_easy_clean.csv : une ligne par fichier brut (gardé / exclu, corrections, raison).
Usage : python ANALYSIS/02_easy_clean.py            -> simulation, écrit seulement le journal
        python ANALYSIS/02_easy_clean.py --apply    -> crée réellement CLEAN_DELINEATION
"""

import csv
import gzip
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from checks import (build_inventory, clean_name, content_hash, failed, fix_orientation,
                    load, passes, read_nifti_bytes)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "DATA" / "DELINEATION_DATA"
CLEAN = ROOT / "DATA" / "CLEAN_DELINEATION"
LOG = ROOT / "RESULTS" / "02_easy_clean.csv"
APPLY = "--apply" in sys.argv


def preference(r):
    """Parmi des copies exactes, garder d'abord le vrai .nii.gz, puis le fichier bien nommé."""
    return (r["extension_ok"] is not True, r["naming_ok"] is not True, r["file"])


def category(reason):
    """Regroupe les raisons d'exclusion pour le résumé (le détail reste dans le journal)."""
    if reason.startswith("labels: ") and ("manquants" in reason or "en trop" in reason):
        return "labels: manquants ou en trop"
    return reason.split(" (")[0].split(" de ")[0]


# ---------------------------------------------------------------- tri des fichiers
print("Lecture des délinéations brutes...")
rows = build_inventory(RAW)
log = {r["file"]: {"original": r["file"], "status": "exclu", "new_file": "",
                   "corrections": "", "reason": ""} for r in rows}
reoriented = {}  # fichier brut -> image réorientée en RAS

candidates = defaultdict(list)  # nom final -> fichiers valides qui y prétendent
for r in rows:
    e = log[r["file"]]
    if r["labels_ok"] is not True:                                   # problème 3
        e["reason"] = failed(r, ["labels"])[0]
        continue
    if r["lr_flip_suspect"] is True:                                 # problème 5
        e["reason"] = "orientation: masque retourné gauche-droite suspect"
        continue
    if r["orientation_ok"] is not True:
        fixed = fix_orientation(load(RAW / r["file"])[1])
        if fixed is None:
            e["reason"] = failed(r, ["orientation"])[0]
            continue
        reoriented[r["file"]] = fixed
    target = clean_name(r["scan"], r["rater"])                       # problème 1
    if target is None:
        e["reason"] = f"naming: sujet ou session inexploitable (lu : {r['scan'] or 'rien'})"
        continue
    candidates[f"{r['group']}\\Rater {r['rater']}\\{target}"].append(r)

kept = {}  # nom final -> ligne d'inventaire du fichier gardé
for target, group in candidates.items():                            # problème 4
    if len({r["content_hash"] for r in group}) > 1:
        for r in group:
            log[r["file"]]["reason"] = "duplicate: contenus différents, tous valides"
        continue
    best, *copies = sorted(group, key=preference)
    kept[target] = best
    best["_dup_fix"] = ("doublon : copie exacte, une seule gardée" if copies
                        else "doublon : seul fichier valide gardé")
    for r in copies:
        log[r["file"]]["reason"] = f"duplicate: copie exacte de {Path(best['file']).name} (gardé)"

for target, r in kept.items():
    e = log[r["file"]]
    e["status"], e["new_file"] = "gardé", target
    fixes = []
    if r["naming_ok"] is not True:                                   # problème 1
        fixes.append("renommé")  # un nom déjà conforme (ses1 -> ses01) est juste harmonisé
    if r["extension_ok"] is not True:                                # problème 2
        fixes.append(f"converti en .nii.gz ({r['extension_detail']})")
    if r["duplicate_ok"] is not True:
        fixes.append(r["_dup_fix"])
    if r["file"] in reoriented:
        fixes.append(f"réorienté en RAS ({r['orientation_detail']})")
    e["corrections"] = " + ".join(fixes)

# ---------------------------------------------------------------- écriture
expected_hash = {}  # nom final -> empreinte attendue des voxels dans CLEAN
if APPLY:
    if CLEAN.exists():
        assert CLEAN.name == "CLEAN_DELINEATION" and CLEAN.parent.name == "DATA"
        shutil.rmtree(CLEAN)  # dossier généré : recréé à chaque exécution
    for target, r in kept.items():
        src, dst = RAW / r["file"], CLEAN / target
        dst.parent.mkdir(parents=True, exist_ok=True)
        if r["file"] in reoriented:
            img = reoriented[r["file"]]
            dst.write_bytes(gzip.compress(img.to_bytes(), compresslevel=6))
            expected_hash[target] = content_hash(np.asarray(img.dataobj))
            continue
        if r["extension_ok"] is True:
            shutil.copy2(src, dst)                                   # déjà un vrai .nii.gz : copie à l'identique
        else:
            dst.write_bytes(gzip.compress(read_nifti_bytes(src), compresslevel=6))
        expected_hash[target] = r["content_hash"]

LOG.parent.mkdir(exist_ok=True)
with open(LOG, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=next(iter(log.values())).keys())
    writer.writeheader()
    writer.writerows(log.values())

# ---------------------------------------------------------------- résumé
entries = list(log.values())
print(("\nCRÉATION EFFECTUÉE" if APPLY else "\nSIMULATION (rien écrit dans DATA, ajouter --apply)") + "\n")
print(f"Gardés : {len(kept)} / {len(entries)} fichiers bruts")
for fix, c in Counter(x for e in entries for x in e["corrections"].split(" + ") if x).most_common():
    print(f"   {c:3d}  {fix}")
print(f"Exclus : {sum(1 for e in entries if e['status'] == 'exclu')}")
for reason, c in Counter(category(e["reason"]) for e in entries if e["status"] == "exclu").most_common():
    print(f"   {c:3d}  {reason}")
print(f"\nJournal : {LOG.relative_to(ROOT)}")

# ---------------------------------------------------------------- vérification
if APPLY:
    print("\nVérification de CLEAN_DELINEATION (tests 1 à 5)...")
    clean_rows = build_inventory(CLEAN)
    bad = [r for r in clean_rows if not passes(r)]
    altered = [r for r in clean_rows if expected_hash.get(r["file"]) != r["content_hash"]]
    print(f"   fichiers           : {len(clean_rows)} (attendu {len(kept)})")
    print(f"   échouent un test   : {len(bad)}")
    for r in bad:
        print(f"      {r['file']} : {r['errors']}")
    print(f"   contenu modifié    : {len(altered)}")
    ok = not bad and not altered and len(clean_rows) == len(kept)
    print("   => OK" if ok else "   => PROBLÈME, voir ci-dessus")
