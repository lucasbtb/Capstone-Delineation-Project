"""
checks.py — Tests de définition des problèmes, réutilisés par tous les scripts d'analyse.

Chaque test renvoie (ok, détail) :
    ok     = True si le fichier passe, False sinon
    détail = texte court qui décrit l'erreur ('' si ok)

Problèmes (voir docs/consigne_analyse.md) :
  1. NAMING      test_naming       nom conforme à naming.md + rater du nom = dossier
  2. EXTENSION   test_extension    vrai fichier .nii.gz (compressé gzip)
  3. LABELS      test_labels       exactement les noyaux 1 à 9 (ni plus, ni moins)
  4. DUPLICATE   find_duplicates   plusieurs fichiers pour le même rater + scan,
                                   copie exacte ou contenu différent
  5. ORIENTATION test_orientation  grille 192x224x224, 1 mm, header RAS
                 find_lr_flips     masque retourné gauche-droite vs les autres raters

Les tests 1, 2, 3, 5 regardent un fichier seul. Les tests 4 et 5b comparent
plusieurs fichiers entre eux : ils sont appliqués par build_inventory().

Point d'entrée principal : build_inventory(dossier) -> une ligne (dict) par fichier.
"""

import gzip
import hashlib
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import nibabel as nib
import numpy as np

PROBLEMS = ["naming", "extension", "labels", "duplicate", "orientation"]

EXPECTED_LABELS = set(range(1, 10))   # 9 noyaux du thalamus, 0 = fond
EXPECTED_SHAPE = (192, 224, 224)      # grille de l'IRM de base
EXPECTED_VOXEL = (1.0, 1.0, 1.0)      # 1 mm isotrope
EXPECTED_ORIENTATION = "RAS"          # axe 0 vers la droite, 1 vers l'avant, 2 vers le haut
VALID_SESSIONS = {"1", "2"}
FLIP_MARGIN = 0.10                    # gain de Dice au-delà duquel le masque retourné est jugé meilleur

# Nom sans extension : SUB + C|G + 3 chiffres _ ses + 1|01|2|02 _ Rater + groupe + lettre _manual_seg
NAME_RULE = re.compile(r"^SUB[CG]\d{3}_ses0?[12]_Rater(\d{1,2}[a-k])_manual_seg$")


# ================================================================ outils
def split_name(filename):
    """Sépare le nom de son extension, même corrompue.
    'X_manual_seg.nii (1).gz' -> ('X_manual_seg', '.nii (1).gz') ; 'X.docx' -> ('X', '.docx')."""
    m = re.search(r"[._]nii", filename)  # tout ce qui suit le premier '.nii' / '_nii' = extension
    if m:
        return filename[:m.start()], filename[m.start():]
    stem, dot, ext = filename.rpartition(".")
    return (stem, "." + ext) if dot else (filename, "")


def scan_key(filename):
    """Scan normalisé 'SUBC001_ses1' lu dans un nom même mal écrit
    (SUBC20, SUBCO20, SUBJEC35, ses01, Session 2, S2...). '?' = partie illisible, None = pas de sujet."""
    sub = re.search(r"SUB(?:JEC)?([CG]?)O?(\d+)", filename, re.I)
    ses = (re.search(r"(?:ses|session)[ _]?0*(\d)", filename, re.I)
           or re.search(r"[_-]S0*(\d)", filename))
    if not sub:
        return None
    group = sub.group(1).upper() or "?"
    session = ses.group(1) if ses else "?"
    return f"SUB{group}{int(sub.group(2)):03d}_ses{session}"


def clean_name(scan, rater):
    """'SUBC001_ses1' + '1a' -> 'SUBC001_ses01_Rater1a_manual_seg.nii.gz'.
    None si le sujet ou la session n'est pas exploitable."""
    m = re.fullmatch(r"SUB([CG])(\d{3})_ses(\d)", scan or "")
    if not m or m.group(3) not in VALID_SESSIONS:
        return None
    return f"SUB{m.group(1)}{m.group(2)}_ses0{m.group(3)}_Rater{rater}_manual_seg.nii.gz"


def read_nifti_bytes(path):
    """Contenu NIfTI brut (non compressé) du fichier, quelle que soit son extension :
    gzip (même mal nommé), zip contenant un .nii, ou .nii brut. None si ce n'est pas un NIfTI."""
    raw = Path(path).read_bytes()
    if raw[:2] == b"PK":  # archive zip
        try:
            with zipfile.ZipFile(path) as z:
                members = [n for n in z.namelist() if ".nii" in n and not n.startswith("__MACOSX")]
                if len(members) != 1:
                    return None
                raw = z.read(members[0])
        except zipfile.BadZipFile:
            return None
    while raw[:2] == b"\x1f\x8b":  # une ou plusieurs couches gzip
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError):
            return None
    is_nifti1 = raw[344:348] in (b"n+1\x00", b"ni1\x00")
    is_nifti2 = raw[4:8] in (b"n+2\x00", b"ni2\x00")
    return raw if (is_nifti1 or is_nifti2) else None


def load(path):
    """Charge le fichier. Retourne (octets NIfTI bruts, image nibabel, voxels) ou (None, None, None)."""
    raw = read_nifti_bytes(path)
    if raw is None:
        return None, None, None
    try:
        cls = nib.Nifti2Image if raw[4:8] in (b"n+2\x00", b"ni2\x00") else nib.Nifti1Image
        img = cls.from_bytes(raw)
        data = np.asarray(img.dataobj)
    except Exception:
        return None, None, None
    return raw, img, data


def content_hash(data):
    """Empreinte du contenu voxel (indépendante du format de fichier) pour repérer les copies exactes."""
    if data is None:
        return ""
    if data.dtype.kind in "iu" or (data.dtype.kind == "f" and np.allclose(data, np.round(data))):
        data = np.round(data).astype(np.int32)  # même masque en uint8 ou float32 = même empreinte
    return hashlib.md5(np.ascontiguousarray(data).tobytes() + str(data.shape).encode()).hexdigest()


def get_labels(data):
    """Valeurs entières non nulles présentes dans le masque (None si ce n'est pas un masque)."""
    if data.dtype.kind == "f":
        if not np.allclose(data, np.round(data)):
            return None  # valeurs non entières = image d'intensité
        data = data.round().astype(np.int64)
    flat = data.ravel()
    values = np.unique(flat) if flat.min() < 0 else np.nonzero(np.bincount(flat))[0]
    return {int(v) for v in values if v != 0}


def dice(a, b):
    total = a.sum() + b.sum()
    return 2 * np.logical_and(a, b).sum() / total if total else np.nan


def downsample(mask):
    """Masque binaire réduit d'un facteur 2 par axe : suffisant pour repérer un retournement."""
    a, b, c = (s // 2 for s in mask.shape)
    return mask[:2 * a, :2 * b, :2 * c].reshape(a, 2, b, 2, c, 2).any(axis=(1, 3, 5))


# ================================================================ 1. nommage
def test_naming(filename, folder_rater):
    stem, _ = split_name(filename)
    m = NAME_RULE.match(stem)
    if not m:
        return False, "nom non conforme"
    if m.group(1) != folder_rater:
        return False, f"rater du nom ({m.group(1)}) != dossier ({folder_rater})"
    return True, ""


# ================================================================ 2. extension
def test_extension(path):
    _, ext = split_name(Path(path).name)
    if ext != ".nii.gz":
        return False, f"extension '{ext}'"
    with open(path, "rb") as f:
        if f.read(2) != b"\x1f\x8b":
            return False, "nommé .nii.gz mais pas compressé"
    return True, ""


# ================================================================ 3. labels
def test_labels(data):
    if data is None:
        return False, "illisible (pas un NIfTI)"
    labels = get_labels(data)
    if labels is None:
        return False, "IRM au lieu du masque"
    if not labels:
        return False, "masque vide"
    missing, extra = EXPECTED_LABELS - labels, labels - EXPECTED_LABELS
    parts = []
    if missing:
        parts.append("manquants " + " ".join(map(str, sorted(missing))))
    if extra:
        parts.append("en trop " + " ".join(map(str, sorted(extra))))
    return (not parts), " ; ".join(parts)


# ================================================================ 5. orientation
def test_orientation(img):
    if img is None:
        return False, "illisible (pas un NIfTI)"
    shape = tuple(int(s) for s in img.shape[:3])
    voxel = tuple(round(float(z), 3) for z in img.header.get_zooms()[:3])
    axes = "".join(nib.aff2axcodes(img.affine))
    parts = []
    if shape != EXPECTED_SHAPE or len(img.shape) != 3:
        parts.append("taille " + "x".join(map(str, img.shape)))
    if not np.allclose(voxel, EXPECTED_VOXEL, atol=0.01):
        parts.append("voxel " + "x".join(map(str, voxel)) + " mm")
    if axes != EXPECTED_ORIENTATION:
        parts.append(f"header {axes}")
    return (not parts), " ; ".join(parts)


def fix_orientation(img):
    """Réoriente l'image en RAS (ordre des voxels + header, la position réelle de chaque
    voxel ne change pas). Retourne l'image corrigée, ou None si la grille reste
    incorrecte après réorientation (mauvaise taille ou taille de voxel)."""
    canon = nib.as_closest_canonical(img)
    return canon if test_orientation(canon)[0] else None


def find_lr_flips(rows, small_masks):
    """5b. Chaque masque est comparé au masque majoritaire des AUTRES raters du même scan,
    tel quel puis retourné gauche-droite (axe 0). Si le retourné colle nettement mieux,
    le masque est probablement inversé. Remplit dice_vs_others, dice_flipped_vs_others,
    lr_flip_suspect (vide = non vérifiable, moins de 2 autres masques)."""
    by_scan = defaultdict(list)
    for i in small_masks:
        if rows[i]["scan"] and "?" not in rows[i]["scan"]:
            by_scan[rows[i]["scan"]].append(i)
    for idx in by_scan.values():
        if len(idx) < 3:
            continue
        total = np.sum([small_masks[i] for i in idx], axis=0, dtype=np.int16)
        for i in idx:
            reference = (total - small_masks[i]) > (len(idx) - 1) / 2
            d = dice(small_masks[i], reference)
            d_flip = dice(small_masks[i][::-1], reference)
            rows[i]["dice_vs_others"] = round(float(d), 3)
            rows[i]["dice_flipped_vs_others"] = round(float(d_flip), 3)
            rows[i]["lr_flip_suspect"] = bool(d_flip > d + FLIP_MARGIN)


# ================================================================ 4. doublons
def find_duplicates(rows):
    """Plusieurs fichiers pour le même rater + scan.
    'copie exacte' = mêmes voxels ; 'contenu différent' sinon (ou fichier illisible)."""
    groups = defaultdict(list)
    for i, r in enumerate(rows):
        if r["scan"]:
            groups[(r["rater"], r["scan"])].append(i)
    for idx in groups.values():
        if len(idx) < 2:
            continue
        hashes = {rows[i]["content_hash"] for i in idx}
        identical = len(hashes) == 1 and "" not in hashes
        kind = "copie exacte" if identical else "contenu différent"
        for i in idx:
            others = [Path(rows[j]["file"]).name for j in idx if j != i]
            rows[i]["duplicate_ok"] = False
            rows[i]["duplicate_detail"] = f"{kind} de {', '.join(others)}"


# ================================================================ inventaire complet
def check_file(path, group, rater, rel):
    """Tous les tests individuels sur un fichier. Retourne (ligne, voxels)."""
    raw, img, data = load(path)
    row = {"group": group, "rater": rater, "file": rel, "scan": scan_key(Path(path).name)}
    labels = get_labels(data) if data is not None else None
    row["labels"] = " ".join(map(str, sorted(labels))) if labels else ""
    for name, (ok, detail) in [
        ("naming", test_naming(Path(path).name, rater)),
        ("extension", test_extension(path)),
        ("labels", test_labels(data)),
        ("duplicate", (True, "")),          # rempli par find_duplicates
        ("orientation", test_orientation(img)),
    ]:
        row[f"{name}_ok"], row[f"{name}_detail"] = ok, detail
    row.update(dice_vs_others="", dice_flipped_vs_others="", lr_flip_suspect="")
    row["content_hash"] = content_hash(data)
    return row, data


def failed(row, problems=PROBLEMS):
    """Erreurs du fichier parmi `problems`, ex. ['naming: nom non conforme', 'labels: manquants 8']."""
    errs = [f"{p}: {row[f'{p}_detail']}" for p in problems if row[f"{p}_ok"] is not True]
    if "orientation" in problems and row["lr_flip_suspect"] is True:
        errs.append("orientation: masque retourné gauche-droite suspect")
    return errs


def passes(row, problems=PROBLEMS):
    """True si le fichier passe tous les tests demandés."""
    return not failed(row, problems)


def build_inventory(data_dir, verbose=False):
    """Applique les 5 tests à tous les fichiers de data_dir/Group N/Rater Nx/...
    Retourne une liste de lignes (dict), une par fichier."""
    data_dir = Path(data_dir)
    rows, small_masks = [], {}
    files = [p for p in sorted(data_dir.rglob("*")) if p.is_file()]
    for k, path in enumerate(files, 1):
        parts = path.relative_to(data_dir).parts
        # strip : sur Mac un dossier s'appelle " Rater 16i" (Windows retire l'espace)
        group, rater = parts[0].strip(), parts[1].strip().replace("Rater ", "")
        row, data = check_file(path, group, rater, str(path.relative_to(data_dir)))
        if data is not None and row["orientation_ok"] and row["labels"]:
            small_masks[len(rows)] = downsample(data > 0)
        rows.append(row)
        if verbose and k % 50 == 0:
            print(f"  {k}/{len(files)} fichiers lus")
    find_duplicates(rows)
    find_lr_flips(rows, small_masks)
    for r in rows:
        r["errors"] = " | ".join(failed(r))
        r["all_ok"] = passes(r)
    return rows
