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
  5. TAILLE   : le volume fait 192×224×224 voxels de 1 mm (grille de l'IRM de base).
  6. GAUCHE / DROITE :
       a. le header déclare l'orientation RAS (sinon gauche et droite peuvent
          être interprétés à l'envers par les logiciels) ;
       b. le masque n'est pas retourné gauche-droite par rapport aux autres
          raters du même scan (comparaison au masque majoritaire, voir plus bas).

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
EXPECTED_SHAPE = (192, 224, 224)      # grille de l'IRM de base
EXPECTED_VOXEL = (1.0, 1.0, 1.0)      # 1 mm isotrope
EXPECTED_ORIENTATION = "RAS"          # axe 0 vers la droite (R), 1 vers l'avant (A), 2 vers le haut (S)
FLIP_MARGIN = 0.10                    # écart de Dice au-delà duquel le masque retourné est jugé meilleur

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
    """Retourne (problème de format ou '', image nibabel ou None, voxels du masque ou None).
    Le volume n'est lu qu'une seule fois ici, puis réutilisé pour les labels."""
    if not path.name.endswith(".nii.gz"):
        issue = "extension"  # .nii, .zip, .docx, .nii.gz.gz, ...
    else:
        with open(path, "rb") as f:
            magic = f.read(2)  # signature gzip = 2 premiers octets, inutile de tout lire
        issue = "" if magic == b"\x1f\x8b" else "pas compressé"  # nommé .gz mais pas gzip
    try:
        img = nib.load(path)
        data = np.asarray(img.dataobj)  # lecture unique du volume
    except Exception:
        return (issue or "illisible"), None, None
    if data.dtype.kind == "f":
        if not np.allclose(data, np.round(data)):  # valeurs non entières = image d'intensité
            return (issue + " + " if issue else "") + "IRM au lieu du masque", img, None
        data = data.round().astype(np.int64)
    return issue, img, data


# ---------------------------------------------------------------- 5. taille
def check_size(img):
    """Retourne (dimensions 'AxBxC', taille de voxel 'a×b×c', conforme ?)."""
    shape = tuple(int(s) for s in img.shape)
    voxel = tuple(round(float(z), 3) for z in img.header.get_zooms()[:3])
    ok = shape == EXPECTED_SHAPE and np.allclose(voxel, EXPECTED_VOXEL, atol=0.01)
    return "x".join(map(str, shape)), "x".join(map(str, voxel)), ok


# ---------------------------------------------------------------- 6. gauche / droite
def check_orientation(img):
    """6a. Orientation déclarée par le header, ex. 'RAS' ou 'LAS' (L = gauche-droite inversé)."""
    return "".join(nib.aff2axcodes(img.affine))


def downsample(mask):
    """Masque binaire (thalamus entier, tous labels) réduit d'un facteur 2 par axe
    (96×112×112) : assez précis pour repérer un retournement, et 8× moins de mémoire."""
    a, b, c = (s // 2 for s in mask.shape)
    return mask.reshape(a, 2, b, 2, c, 2).any(axis=(1, 3, 5))


def dice(a, b):
    total = a.sum() + b.sum()
    return 2 * np.logical_and(a, b).sum() / total if total else np.nan


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
small_masks = {}  # index de la ligne -> masque réduit, pour la vérification 6b
for path in sorted(DATA.rglob("*")):
    if not path.is_file():
        continue
    group = path.relative_to(DATA).parts[0]                          # "Group 1"
    rater = path.relative_to(DATA).parts[1].replace("Rater ", "")    # "1a"

    name_ok, rater_match = check_name(path.name, rater)
    format_issue, img, data = check_format(path)
    labels = get_labels(data) if data is not None else None

    shape, voxel, size_ok = check_size(img) if img is not None else ("", "", False)
    orientation = check_orientation(img) if img is not None else ""
    if data is not None and size_ok and data.any():
        small_masks[len(rows)] = downsample(data > 0)

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
        "shape": shape,
        "voxel_mm": voxel,
        "size_ok": size_ok,
        "orientation": orientation,
        "orientation_ok": orientation == EXPECTED_ORIENTATION,
        "dice_vs_others": "",
        "dice_flipped_vs_others": "",
        "lr_flip_suspect": "",  # vide = non vérifiable (moins de 2 autres masques du scan)
    })

# ---------------------------------------------------------------- 6b. masque retourné
# Pour chaque scan, chaque masque est comparé au masque majoritaire des AUTRES raters
# du même scan (voxel retenu si > 50 % d'entre eux l'ont colorié), tel quel puis
# retourné gauche-droite (axe 0). Si la version retournée colle nettement mieux,
# le masque est probablement inversé. Comparaison faite en coordonnées voxel,
# donc indépendante des erreurs de header.
# Limite : si le thalamus est pile au centre du volume, retourné ou non donne
# le même Dice, et le retournement est alors indétectable (et sans effet sur le masque global).
by_scan = {}
for i in small_masks:
    if rows[i]["scan"] and "?" not in rows[i]["scan"]:
        by_scan.setdefault(rows[i]["scan"], []).append(i)
for scan, idx in by_scan.items():
    if len(idx) < 3:  # il faut au moins 2 autres masques pour une majorité
        continue
    total = np.sum([small_masks[i] for i in idx], axis=0, dtype=np.int16)
    for i in idx:
        others = total - small_masks[i]
        reference = others > (len(idx) - 1) / 2
        d = dice(small_masks[i], reference)
        d_flip = dice(small_masks[i][::-1], reference)
        rows[i]["dice_vs_others"] = round(float(d), 3)
        rows[i]["dice_flipped_vs_others"] = round(float(d_flip), 3)
        rows[i]["lr_flip_suspect"] = bool(d_flip > d + FLIP_MARGIN)

# ---------------------------------------------------------------- 3. doublons
# Même rater + même scan normalisé, sur plusieurs fichiers.
counts = Counter((r["rater"], r["scan"]) for r in rows if r["scan"])
for r in rows:
    r["duplicate"] = r["scan"] is not None and counts[(r["rater"], r["scan"])] > 1
    # Fichier exploitable tel quel = toutes les vérifications passent.
    r["all_ok"] = (r["name_ok"] and r["format_ok"] and not r["duplicate"] and r["labels_ok"]
                   and r["size_ok"] and r["orientation_ok"] and r["lr_flip_suspect"] is not True)

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

print(f"\n5. Taille 192x224x224, 1 mm : {count('size_ok')}/{n}")
for (shape, voxel), c in Counter((r["shape"], r["voxel_mm"]) for r in rows
                                 if not r["size_ok"] and r["shape"]).most_common():
    print(f"   {shape} voxels de {voxel} mm : {c}")

print(f"\n6a. Orientation header RAS : {count('orientation_ok')}/{n}")
for o, c in Counter(r["orientation"] for r in rows
                    if not r["orientation_ok"] and r["orientation"]).most_common():
    print(f"   {o} : {c}")
checked = [r for r in rows if r["lr_flip_suspect"] != ""]
print(f"6b. Masque retourné G-D suspect : {count('lr_flip_suspect')}/{len(checked)} vérifiés")
for r in rows:
    if r["lr_flip_suspect"] is True:
        print(f"   {r['file']}  (Dice {r['dice_vs_others']} -> {r['dice_flipped_vs_others']} retourné)")

print(f"\nExploitables tels quels (tout OK) : {count('all_ok')}/{n}")
print(f"Détail : {OUT.relative_to(ROOT)}")
