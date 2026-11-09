"""
build_viewer.py — Prépare le site local de comparaison des délinéations.

Pour chaque sujet, lit toutes les délinéations exploitables (tous raters,
toutes sessions), garde uniquement les voxels non nuls dans la boîte englobante
commune du sujet, et écrit :
  RESULTS/viewer/index.html          (copie de ANALYSIS/viewer/index.html)
  RESULTS/viewer/data/index.js       (liste des sujets)
  RESULTS/viewer/data/<SUJET>.js     (masques du sujet, encodés en base64)

Chaque délinéation porte son statut lu dans RESULTS/02_clean_name.csv
(1_correct, 2_nom, non_traite + raison), ce qui permet de filtrer dans l'appli
entre données brutes et données propres. Pour les fichiers propres, le sujet
et la session viennent du nom corrigé par 02_clean_name.py.
Relancer ce script après 02_clean_name.py pour mettre les statuts à jour.

Ouvrir ensuite RESULTS/viewer/index.html dans un navigateur (aucun serveur,
aucune donnée envoyée en ligne). Ne modifie aucun fichier de DATA/.

Usage : .venv/bin/python ANALYSIS/viewer/build_viewer.py [SUJET ...]
        (sans argument = tous les sujets)
"""

import base64
import csv
import json
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # delineation_io.py est à côté
from delineation_io import (ROOT, EXPECTED_LABELS, NUCLEI, list_files,  # noqa: E402
                            load_volume, classify, labels_present, parse_name)

HERE = Path(__file__).resolve().parent
OUT = ROOT / "RESULTS" / "viewer"
CLEAN_LOG = ROOT / "RESULTS" / "02_clean_name.csv"
MARGIN = 12  # voxels autour du cadre
NAME_RULE = re.compile(r"^SUB[CG]\d{3}_ses0?[12]_Rater(\d{1,2}[a-k])_manual_seg\.nii\.gz$")


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode("ascii")


def safe(subject):
    return subject.replace("?", "X")


def norm(p):
    """Chemin comparable entre Mac et Windows : séparateur '/' et espaces retirés
    autour de chaque dossier (Windows supprime ceux de ' Rater 16i', 'delineated ')."""
    return "/".join(part.strip() for part in p.replace("\\", "/").split("/"))


def load_clean_log():
    """{chemin d'origine: ligne du journal 02_clean_name.csv} ; vide si absent."""
    if not CLEAN_LOG.exists():
        print(f"⚠ {CLEAN_LOG.name} absent : statut 'absent' pour tous les fichiers")
        return {}
    with open(CLEAN_LOG, encoding="utf-8") as f:
        return {norm(r["original"]): r for r in csv.DictReader(f)}


def attach_status(f, log):
    """Ajoute step / reason / clean_file ; sujet et session du nom corrigé si propre."""
    r = log.get(norm(f["file"]))
    f["step"] = r["step"] if r else "absent"
    f["reason"] = (r["reason"] if r else "absent de 02_clean_name.csv") or ""
    f["clean_file"] = norm(r["new_file"]) if r and r["new_file"] else ""
    if f["clean_file"]:
        f["subject"], f["session"] = parse_name(Path(f["clean_file"]).name)
    return f


def issues_of(f, labels, note):
    out = []
    m = NAME_RULE.match(Path(f["file"]).name)
    if not m:
        out.append("nom non conforme")
    elif m.group(1) != f["rater"]:
        out.append("rater du nom ≠ dossier")
    if note:
        out.append("fichier mal compressé")
    if labels != EXPECTED_LABELS:
        out.append("labels : " + (" ".join(map(str, labels)) or "aucun"))
    return out


def build_subject(subject, files):
    vols, metas = [], []
    for f in files:
        try:
            data, note = load_volume(f["path"])
        except Exception:
            continue
        if classify(data) != "masque":
            continue  # IRM au lieu du masque, vide
        data = np.rint(data).astype(np.int64)
        labels = labels_present(data)
        vols.append(data)
        metas.append({
            "rater": f["rater"], "group": f["group"].replace("Group ", ""),
            "session": f["session"], "file": f["file"], "labels": labels,
            "nvox": int(np.count_nonzero(data)), "issues": issues_of(f, labels, note),
            "step": f["step"], "reason": f["reason"], "clean_file": f["clean_file"],
        })
    if not vols:
        return None

    # Cadre commun = percentiles 0.1–99.9 % des voxels de toutes les délinéations
    # (des voxels parasites loin du thalamus étireraient sinon le cadre).
    # Les voxels hors cadre sont comptés et signalés dans "issues".
    shape = vols[0].shape
    coords = np.concatenate([np.argwhere(v != 0) for v in vols])
    lo = [max(0, int(np.percentile(coords[:, a], 0.1)) - MARGIN) for a in range(3)]
    hi = [min(shape[a], int(np.percentile(coords[:, a], 99.9)) + 1 + MARGIN) for a in range(3)]
    nx, ny, nzz = (h - l for l, h in zip(lo, hi))
    for v, m in zip(vols, metas):
        inside = int(np.count_nonzero(v[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]))
        if m["nvox"] - inside:
            m["issues"].append(f"{m['nvox'] - inside} voxels loin du thalamus (non affichés)")

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
    log = load_clean_log()
    by_subject = defaultdict(list)
    for f in list_files():
        if f["is_nifti_like"]:
            attach_status(f, log)
            if f["subject"]:
                by_subject[f["subject"]].append(f)

    (OUT / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "index.html", OUT / "index.html")

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
        "window.VIEWER_NUCLEI=" + json.dumps(nuclei) + ";\nwindow.VIEWER_INDEX="
        # sujets "SUB?" (lettre C/G absente du nom) en fin de liste
        + json.dumps(sorted(index.values(), key=lambda s: ("?" in s["subject"], s["subject"])), indent=0) + ";",
        encoding="utf-8")
    print(f"\nOuvrir : {OUT / 'index.html'}")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
