"""
01_inventory.py — Inventaire des délinéations manuelles (lecture seule).

Pour chaque fichier de DATA/DELINEATION_DATA, vérifie 4 choses :
  1. NOMMAGE  : le nom respecte la consigne (given_documents/naming.md)
                SUBJECTID_SESSION_RATERID_manual_seg.nii.gz
                ex. SUBC001_ses01_Rater1a_manual_seg.nii.gz
                + le rater du nom correspond au dossier où le fichier est rangé.
  2. FORMAT   : le fichier est un vrai NIfTI compressé (.nii.gz) lisible,
                et contient une segmentation (valeurs entières), pas une IRM.
  3. DOUBLONS : un même rater a rendu plusieurs fichiers pour le même scan
                (sujet + session, après normalisation du nom).
  4. LABELS   : le masque contient exactement les labels 1 à 9.

Sorties :
  - un résumé dans le terminal ;
  - RESULTS/01_inventory.csv : une ligne par fichier, une colonne par vérification.

Ne modifie aucun fichier de données.
Usage : python ANALYSIS/01_inventory.py
"""

import csv
import re
from collections import Counter
from pathlib import Path

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "DATA" / "DELINEATION_DATA"
OUT = ROOT / "RESULTS" / "01_inventory.csv"

EXPECTED_LABELS = list(range(1, 10))  # 9 noyaux du thalamus, 0 = fond

# Consigne exacte : SUB + C|G + 3 chiffres _ ses + 1 ou 01 / 2 ou 02 _ Rater + n° groupe + lettre _manual_seg.nii.gz
NAME_RULE = re.compile(r"^SUB[CG]\d{3}_ses0?[12]_Rater(\d{1,2}[a-k])_manual_seg\.nii\.gz$")


# ---------------------------------------------------------------- 1. nommage
def check_name(filename, folder_rater):
    """Retourne (nom conforme ?, rater du nom == dossier ?)."""
    m = NAME_RULE.match(filename)
    if not m:
        return False, None  # rater illisible si le nom n'est pas conforme
    return True, m.group(1) == folder_rater


def scan_key(filename):
    """Identifiant normalisé 'SUBC001_ses1' extrait d'un nom même mal écrit.
    Tolère : SUBC20, SUBCO20 (lettre O), SUBJEC35, ses01 / Session1 / SESSION01 / S2."""
    sub = re.search(r"SUB(?:JEC)?([CG]?)O?(\d+)", filename, re.I)
    ses = re.search(r"(?:ses|session)[ _]?0*(\d)", filename, re.I) or re.search(r"_S(\d)", filename)
    if not sub:
        return None
    group = sub.group(1).upper() or "?"  # '?' = lettre C/G absente du nom
    session = ses.group(1) if ses else "?"
    return f"SUB{group}{int(sub.group(2)):03d}_ses{session}"


# ---------------------------------------------------------------- 2. format
def check_format(path):
    """Retourne (problème de format ou '', voxels du masque ou None).
    Le volume n'est lu qu'une seule fois ici, puis réutilisé pour les labels."""
    if not path.name.endswith(".nii.gz"):
        issue = "extension"  # .nii, .zip, .docx, .nii.gz.gz, ...
    else:
        with open(path, "rb") as f:
            magic = f.read(2)  # signature gzip = 2 premiers octets, inutile de tout lire
        issue = "" if magic == b"\x1f\x8b" else "pas compressé"  # nommé .gz mais pas gzip
    try:
        data = np.asarray(nib.load(path).dataobj)  # lecture unique du volume
    except Exception:
        return (issue or "illisible"), None
    if data.dtype.kind == "f":
        if not np.allclose(data, np.round(data)):  # valeurs non entières = image d'intensité
            return (issue + " + " if issue else "") + "IRM au lieu du masque", None
        data = data.round().astype(np.int64)
    return issue, data


# ---------------------------------------------------------------- 4. labels
def get_labels(data):
    """Labels présents (hors 0). np.bincount compte chaque valeur entière sans trier
    les ~10 M voxels, bien plus rapide que np.unique ; np.unique reste en secours
    si le masque contient des valeurs négatives (bincount ne les accepte pas)."""
    flat = data.ravel()
    values = np.unique(flat) if flat.min() < 0 else np.nonzero(np.bincount(flat))[0]
    return [int(v) for v in values if v != 0]


# ---------------------------------------------------------------- main
rows = []
for path in sorted(DATA.rglob("*")):
    if not path.is_file():
        continue
    group = path.relative_to(DATA).parts[0]                          # "Group 1"
    rater = path.relative_to(DATA).parts[1].replace("Rater ", "")    # "1a"

    name_ok, rater_match = check_name(path.name, rater)
    format_issue, data = check_format(path)
    labels = get_labels(data) if data is not None else None

    rows.append({
        "group": group,
        "rater": rater,
        "file": str(path.relative_to(DATA)),
        "scan": scan_key(path.name),
        "name_ok": name_ok,
        "rater_match_folder": rater_match,
        "format_ok": format_issue == "",
        "format_issue": format_issue,
        "n_labels": len(labels) if labels is not None else "",
        "labels": " ".join(map(str, labels)) if labels is not None else "",
        "labels_ok": labels == EXPECTED_LABELS,
    })

# ---------------------------------------------------------------- 3. doublons
# Même rater + même scan normalisé, sur plusieurs fichiers.
counts = Counter((r["rater"], r["scan"]) for r in rows if r["scan"])
for r in rows:
    r["duplicate"] = r["scan"] is not None and counts[(r["rater"], r["scan"])] > 1
    # Fichier exploitable tel quel = les 4 vérifications passent.
    r["all_ok"] = r["name_ok"] and r["format_ok"] and not r["duplicate"] and r["labels_ok"]

OUT.parent.mkdir(exist_ok=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

# ---------------------------------------------------------------- résumé
n = len(rows)
def count(key):
    return sum(1 for r in rows if r[key] is True)

print(f"Fichiers trouvés : {n}  ({len({r['rater'] for r in rows})} raters avec au moins un fichier)\n")

print(f"1. Nommage conforme       : {count('name_ok')}/{n}")
print(f"   dont rater du nom != dossier : {sum(1 for r in rows if r['rater_match_folder'] is False)}")

print(f"\n2. Format conforme        : {count('format_ok')}/{n}")
for issue, c in Counter(r["format_issue"] for r in rows if not r["format_ok"]).most_common():
    print(f"   {issue:30s} {c}")

dup_scans = {k for k, c in counts.items() if c > 1}
print(f"\n3. Doublons               : {count('duplicate')} fichiers pour {len(dup_scans)} scans")

print(f"\n4. Labels = 1..9          : {count('labels_ok')}/{n}")
wrong = Counter(r["n_labels"] for r in rows if not r["labels_ok"] and r["n_labels"] != "")
for k in sorted(wrong):
    print(f"   {k:2d} labels (pas 1..9) : {wrong[k]} fichiers")
print(f"   non vérifiable (illisible ou IRM) : {sum(1 for r in rows if r['n_labels'] == '')} fichiers")

print(f"\nExploitables tels quels (4 OK) : {count('all_ok')}/{n}")
print(f"Détail : {OUT.relative_to(ROOT)}")
