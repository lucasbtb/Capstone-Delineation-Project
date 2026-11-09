"""
delineation_io.py — Lecture des délinéations pour le viewer (lecture seule).

Utilisé par ANALYSIS/viewer/build_viewer.py. Voir DOCUMENTATION/viewer.md.

Ne modifie aucun fichier de données : les fichiers mal compressés (.nii.gz.gz,
.zip, faux .gz, "nii (1).gz", ...) sont décompressés en mémoire uniquement.
"""

import gzip
import io
import re
import zipfile
from pathlib import Path

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]  # ANALYSIS/viewer/ -> racine du projet
DATA = ROOT / "DATA" / "DELINEATION_DATA"

EXPECTED_LABELS = list(range(1, 10))  # 9 noyaux, 0 = fond

# Ordre de DOCUMENTATION/given_documents/colors.md. La correspondance
# label <-> noyau n'est PAS confirmée (cf. potential_problem.md) : hypothèse
# label 1 = 1er noyau de la liste, etc.
NUCLEI = [
    ("LGN", "#40e0d0"),       # turquoise
    ("MGN", "#ff69b4"),       # rose
    ("Pulvinar", "#ffd700"),  # jaune
    ("AV", "#e32626"),        # rouge
    ("VA", "#2eb82e"),        # vert
    ("VLA/VLP", "#2a6fdb"),   # bleu
    ("VPL", "#8b5a2b"),       # marron
    ("MD", "#8e44ad"),        # violet
    ("CM", "#ff8c00"),        # orange
]


# ---------------------------------------------------------------- nommage
def parse_name(filename):
    """Extrait (sujet, session) d'un nom même mal écrit.
    Même logique que scan_key() de 01_inventory.py :
    tolère SUBC20, SUBCO20 (lettre O), SUBJEC35, ses01 / Session1 / S2.
    Retourne ('SUBC001', '1') ; 'SUB?008' si la lettre C/G manque ;
    session '?' si illisible ; (None, None) si aucun sujet trouvé."""
    sub = re.search(r"SUB(?:JEC)?([CG]?)O?(\d+)", filename, re.I)
    ses = (re.search(r"(?:ses|session)[ _]?0*(\d)", filename, re.I)
           or re.search(r"[_-]S(\d)", filename))
    if not sub:
        return None, None
    group = sub.group(1).upper() or "?"
    return f"SUB{group}{int(sub.group(2)):03d}", (ses.group(1) if ses else "?")


def list_files():
    """Tous les fichiers de DATA/DELINEATION DATA avec groupe / rater du dossier."""
    rows = []
    for path in sorted(DATA.rglob("*")):
        if not path.is_file() or path.name == ".DS_Store":
            continue
        rel = path.relative_to(DATA)
        subject, session = parse_name(path.name)
        rows.append({
            "path": path,
            "file": str(rel),
            "group": rel.parts[0].strip(),
            "rater": rel.parts[1].strip().replace("Rater ", ""),  # dossier " Rater 16i"
            "subject": subject,
            "session": session,
            # "nii" n'importe où (couvre .nii, .nii.gz, _nii.gz, .nii.zip) ; exclut .docx
            "is_nifti_like": "nii" in path.name.lower(),
        })
    return rows


# ---------------------------------------------------------------- lecture
def _unwrap(raw):
    """Retire les couches gzip / zip successives (ex. .nii.gz.gz)."""
    for _ in range(5):
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        elif raw[:4] == b"PK\x03\x04":
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names = [n for n in z.namelist() if ".nii" in n and not n.startswith("__MACOSX")]
                raw = z.read(names[0])
        else:
            return raw
    return raw


def load_volume(path):
    """Charge un NIfTI quelle que soit son extension réelle.
    Retourne (array, note) ; note = '' si lecture standard, sinon explication."""
    try:
        return np.asarray(nib.load(path).dataobj), ""
    except Exception:
        pass
    raw = _unwrap(Path(path).read_bytes())
    img = nib.Nifti1Image.from_bytes(raw)  # lève une exception si vraiment illisible
    return np.asarray(img.dataobj), "lu après décompression manuelle"


def classify(data):
    """Type de contenu : 'masque', 'IRM au lieu du masque', 'vide'."""
    if data.dtype.kind == "f" and not np.allclose(data, np.round(data)):
        return "IRM au lieu du masque"
    if not np.any(data):
        return "vide"
    return "masque"


def labels_present(data):
    flat = data.ravel().astype(np.int64)
    values = np.unique(flat) if flat.min() < 0 else np.nonzero(np.bincount(flat))[0]
    return [int(v) for v in values if v != 0]
