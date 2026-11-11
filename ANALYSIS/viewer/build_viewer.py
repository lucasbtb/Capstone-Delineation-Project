"""
build_viewer.py — Prépare le site local de comparaison des délinéations.

Pour chaque sujet, lit toutes les délinéations brutes lisibles (tous raters,
toutes sessions), garde uniquement les voxels non nuls dans la boîte englobante
commune du sujet, et écrit :
  RESULTS/viewer/index.html          (copie de ANALYSIS/viewer/index.html)
  RESULTS/viewer/data/index.js       (liste des sujets)
  RESULTS/viewer/data/<SUJET>.js     (masques du sujet, encodés en base64)

Lecture des fichiers et des noms : mêmes fonctions que l'analyse (ANALYSIS/checks.py).
Chaque délinéation porte :
  - son statut, lu dans RESULTS/02_easy_clean.csv :
      propre  = gardé sans correction      corrige = gardé après correction
      exclu   = hors de CLEAN_DELINEATION  absent  = pas dans le journal
  - ses erreurs, lues dans RESULTS/01_inventory.csv (colonne 'errors').
  - des contrôles calculés ici (aide à la détection, pas encore dans checks.py) :
      volume de chaque label par côté (G/D), fragments (morceaux séparés du bloc
      principal), trous entre coupes, voxels hors du cadre affiché.
Pour les fichiers gardés, le sujet et la session viennent du nom corrigé.
Relancer ce script après 01_inventory.py et 02_easy_clean.py.

Ouvrir ensuite RESULTS/viewer/index.html dans un navigateur (aucun serveur,
aucune donnée envoyée en ligne). Ne modifie aucun fichier de DATA/.

Usage : python ANALYSIS/viewer/build_viewer.py [SUJET ...]   (sans argument = tous les sujets)
"""

import base64
import csv
import json
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # checks.py est dans ANALYSIS/
from checks import get_labels, load, scan_key  # noqa: E402
import build_tables  # noqa: E402  (même dossier que ce script)

ROOT = HERE.parents[1]
DATA = ROOT / "DATA" / "DELINEATION_DATA"
OUT = ROOT / "RESULTS" / "viewer"
INVENTORY = ROOT / "RESULTS" / "01_inventory.csv"
CLEAN_LOG = ROOT / "RESULTS" / "02_easy_clean.csv"
MARGIN = 12  # voxels autour du cadre
STRUCT = np.ones((3, 3, 3), bool)  # 26-connexité : deux voxels qui se touchent par un coin = même morceau
ISOLATED_MM = 3  # fragment à plus de 3 mm de son bloc principal = "isolé" (sinon "détaché")
MAX_FRAGS = 200  # fragments détaillés par délinéation (les comptes restent exacts)
MAX_FAR = 50000  # voxels hors cadre transmis à la page

# Ordre de DOCUMENTATION/given_documents/colors.md. La correspondance
# label <-> noyau n'est PAS confirmée : hypothèse label 1 = 1er noyau de la liste, etc.
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


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode("ascii")


def safe(subject):
    return subject.replace("?", "X")


def norm(p):
    """Chemin comparable entre Mac et Windows : séparateur '/' et espaces retirés
    autour de chaque dossier (Windows supprime ceux de ' Rater 16i', 'delineated ')."""
    return "/".join(part.strip() for part in p.replace("\\", "/").split("/"))


def read_csv(path):
    """{chemin normalisé: ligne} ; vide (avec avertissement) si le fichier manque."""
    if not path.exists():
        print(f"⚠ {path.name} absent : lancer 01_inventory.py puis 02_easy_clean.py")
        return {}
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    key = "original" if "original" in rows[0] else "file"
    return {norm(r[key]): r for r in rows}


def subject_session(filename):
    """'SUBC001_ses01_...' -> ('SUBC001', '1') via scan_key de checks.py."""
    scan = scan_key(filename)
    if not scan:
        return None, None
    subject, session = scan.split("_ses")
    return subject, session


def list_files(inventory, log):
    """Fichiers bruts avec groupe / rater du dossier, statut et erreurs."""
    files = []
    for path in sorted(DATA.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(DATA)
        f = {"path": path, "file": str(rel), "group": rel.parts[0].strip(),
             "rater": rel.parts[1].strip().replace("Rater ", "")}
        inv, e = inventory.get(norm(f["file"])), log.get(norm(f["file"]))
        if not e:
            f["step"], f["reason"], f["clean_file"] = "absent", "absent de 02_easy_clean.csv", ""
        else:
            kept = e["status"] == "gardé"
            f["step"] = ("corrige" if e["corrections"] else "propre") if kept else "exclu"
            f["reason"] = e["corrections"] if kept else e["reason"]
            f["clean_file"] = norm(e["new_file"]) if kept else ""
        f["issues"] = inv["errors"].split(" | ") if inv and inv["errors"] else []
        name = Path(f["clean_file"]).name if f["clean_file"] else path.name
        f["subject"], f["session"] = subject_session(name)
        files.append(f)
    return files


def gaps_of(pts, lo):
    """Coupes vides entre la première et la dernière coupe occupée, sur chaque axe."""
    out = []
    for a in range(3):
        vals = np.unique(pts[:, a])
        for i in np.nonzero(np.diff(vals) > 1)[0]:
            out.append([a, int(vals[i] + 1 + lo[a]), int(vals[i + 1] - 1 + lo[a])])
    return out


def controls(data):
    """Contrôles par label et par côté. Chaque label est bilatéral : un bloc principal
    à gauche, un à droite (côté = centre du morceau par rapport au centre gauche-droite
    de la délinéation ; RAS : x petit = gauche). Tout autre morceau est un fragment.
    Coordonnées renvoyées : voxels du volume d'origine."""
    coords = np.argwhere(data)
    lo, hi = coords.min(0), coords.max(0) + 1
    crop = data[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    cx = coords[:, 0].mean() - lo[0]
    stats, gaps, frags = {}, [], []
    nfrag = [0, 0, 0, 0]  # isolés, détachés, voxels isolés, voxels détachés
    for l in np.unique(crop[crop != 0]):
        l = int(l)
        comp, n = ndimage.label(crop == l, STRUCT)
        pts = np.argwhere(comp)
        ids = comp[tuple(pts.T)] - 1
        sizes = np.bincount(ids, minlength=n)
        cents = np.zeros((n, 3))
        np.add.at(cents, ids, pts)
        cents /= sizes[:, None]
        side = np.where(cents[:, 0] < cx, "G", "D")
        stats[str(l)] = {}
        for s in ("G", "D"):
            members = np.nonzero(side == s)[0]
            if not len(members):
                continue
            main = members[np.argmax(sizes[members])]
            tot = int(sizes[members].sum())
            c = (cents[members] * sizes[members, None]).sum(0) / tot + lo
            stats[str(l)][s] = [tot] + [int(round(v)) for v in c]
            keep = ids == main
            others = members[members != main]
            if len(others):
                in_frag = np.isin(ids, others)
                d, _ = cKDTree(pts[ids == main]).query(pts[in_frag])
                dmin = np.full(n, np.inf)
                np.minimum.at(dmin, ids[in_frag], d)
                for j in others:
                    iso = bool(dmin[j] > ISOLATED_MM)
                    nfrag[0 if iso else 1] += 1
                    nfrag[2 if iso else 3] += int(sizes[j])
                    frags.append([l, s, int(sizes[j])] + [int(round(v)) for v in cents[j] + lo]
                                 + [round(float(dmin[j]), 1)])
                    if not iso:
                        keep |= ids == j
            # trous : sur le bloc principal + fragments proches (les isolés sont listés à part)
            gaps += [[l, s] + g for g in gaps_of(pts[keep], lo)]
    frags.sort(key=lambda f: (f[6] <= ISOLATED_MM, -f[2]))
    return {"stats": stats, "gaps": gaps, "frags": frags[:MAX_FRAGS], "nfrag": nfrag}


def build_subject(subject, files):
    vols, metas = [], []
    for f in files:
        _, _, data = load(f["path"])
        labels = get_labels(data) if data is not None else None
        if not labels:
            continue  # illisible, IRM au lieu du masque, vide
        data = np.rint(data).astype(np.int64)
        vols.append(data)
        metas.append({
            "rater": f["rater"], "group": f["group"].replace("Group ", ""),
            "session": f["session"], "file": f["file"], "labels": sorted(labels),
            "nvox": int(np.count_nonzero(data)), "issues": list(f["issues"]),
            "step": f["step"], "reason": f["reason"], "clean_file": f["clean_file"],
            **controls(data),
        })
    if not vols:
        return None

    # Cadre commun = percentiles 0.1–99.9 % des voxels de toutes les délinéations
    # (des voxels parasites loin du thalamus étireraient sinon le cadre).
    # Les voxels hors cadre sont transmis à part : la page les montre en rouge
    # dans la vue d'ensemble (volume entier).
    shape = vols[0].shape
    coords = np.concatenate([np.argwhere(v != 0) for v in vols])
    lo = [max(0, int(np.percentile(coords[:, a], 0.1)) - MARGIN) for a in range(3)]
    hi = [min(shape[a], int(np.percentile(coords[:, a], 99.9)) + 1 + MARGIN) for a in range(3)]
    nx, ny, nzz = (h - l for l, h in zip(lo, hi))
    for v, m in zip(vols, metas):
        pts = np.argwhere(v)
        far = pts[~((pts >= lo) & (pts < hi)).all(1)]
        m["nfar"] = len(far)
        far = far[:MAX_FAR]
        m["far"] = b64(far.astype("<u2"))
        m["far_lab"] = b64(np.clip(v[tuple(far.T)], 0, 65535).astype("<u2"))

    dels = []
    order = sorted(range(len(vols)), key=lambda i: (metas[i]["session"] or "", metas[i]["group"].zfill(2), metas[i]["rater"]))
    for i in order:
        crop = vols[i][lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
        x, y, z = np.nonzero(crop)
        idx = (x + nx * (y + ny * z)).astype("<u4")  # index plat, x varie le plus vite
        lab = np.clip(crop[x, y, z], 0, 65535).astype("<u2")
        dels.append({**metas[i], "idx": b64(idx), "lab": b64(lab)})

    return {"subject": subject, "shape": list(shape),
            "bbox": {"x0": lo[0], "y0": lo[1], "z0": lo[2], "nx": nx, "ny": ny, "nz": nzz},
            "dels": dels}


def main(only):
    by_subject = defaultdict(list)
    for f in list_files(read_csv(INVENTORY), read_csv(CLEAN_LOG)):
        if f["subject"]:
            by_subject[f["subject"]].append(f)

    (OUT / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "index.html", OUT / "index.html")
    build_tables.main()  # lecteur de CSV : RESULTS/viewer/tables.html

    index_path = OUT / "data" / "index.js"
    index = {}
    if index_path.exists() and only:  # mise à jour partielle : garder les autres sujets
        txt = index_path.read_text(encoding="utf-8")
        txt = txt[txt.index("window.VIEWER_INDEX=") + len("window.VIEWER_INDEX="):].rstrip().rstrip(";")
        index = {s["subject"]: s for s in json.loads(txt)}

    for subject in sorted(by_subject):
        if only and subject not in only:
            continue
        payload = build_subject(subject, by_subject[subject])
        if payload is None:
            continue
        name = safe(subject)
        (OUT / "data" / f"{name}.js").write_text(
            f"window.VIEWER_DATA=window.VIEWER_DATA||{{}};window.VIEWER_DATA[{json.dumps(subject)}]="
            + json.dumps(payload, separators=(",", ":")) + ";", encoding="utf-8")
        # (session, statut) de chaque délinéation : l'appli compte selon le filtre choisi
        index[subject] = {"subject": subject, "file": name,
                          "dels": [[d["session"], d["step"]] for d in payload["dels"]]}
        print(f"{subject:8s} {len(payload['dels']):2d} délinéations")

    nuclei = [{"label": i + 1, "name": n, "color": c} for i, (n, c) in enumerate(NUCLEI)]
    index_path.write_text(
        # VIEWER_BUILD : ajouté à l'URL des fichiers sujets pour que le navigateur
        # ne réutilise pas une ancienne version en cache après un nouveau build
        f"window.VIEWER_BUILD={int(time.time())};\n"
        f"window.VIEWER_PARAMS={json.dumps({'isolated_mm': ISOLATED_MM})};\n"
        "window.VIEWER_NUCLEI=" + json.dumps(nuclei) + ";\nwindow.VIEWER_INDEX="
        # sujets "SUB?" (lettre C/G absente du nom) en fin de liste
        + json.dumps(sorted(index.values(), key=lambda s: ("?" in s["subject"], s["subject"])), indent=0) + ";",
        encoding="utf-8")
    print(f"\nOuvrir : {OUT / 'index.html'}")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
