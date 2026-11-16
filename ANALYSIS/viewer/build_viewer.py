"""
build_viewer.py — Prepares the local website for comparing delineations.

Shows, for each subject:
  - every delineation of DATA/DELINEATION_CLEAN (output of build_clean_data.py), as listed in its
    delineations.csv. Status, from RESULTS/build_clean_data_report.csv (column new_file):
      clean    = copied unchanged from the raw data
      fixed    = copied with a change (converted, reoriented, name corrected), reason shown
  - every raw file of DATA/DELINEATION_DATA that build_clean_data.py did not copy (build_clean_data_report.csv,
    action "not copied"): status excluded, with the reason.
Keeps only the non-zero voxels inside the subject's common bounding box, and writes:
  RESULTS/viewer/index.html          (copy of ANALYSIS/viewer/index.html)
  RESULTS/viewer/data/index.js       (list of subjects)
  RESULTS/viewer/data/<SUBJECT>.js   (masks of the subject, base64-encoded)
Also computes exploratory checks (help to detect problems, not in the cleaning yet):
  volume of each label per side (L/R), fragments (pieces separate from the main block),
  gaps between slices, voxels outside the displayed frame.
Files and names are read with the shared functions of ANALYSIS/helpers.py.
Rerun this script after build_clean_data.py.

Then open RESULTS/viewer/index.html in a browser (no server, no data sent online).
Does not modify any file of DATA/.

Usage: python ANALYSIS/viewer/build_viewer.py [SUBJECT ...]   (e.g. C_001; no argument = every subject)
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
sys.path.insert(0, str(HERE.parent))  # helpers.py is in ANALYSIS/
from helpers import get_labels, load, scan_key  # noqa: E402
import build_tables  # noqa: E402  (same folder as this script)

ROOT = HERE.parents[1]
DATA = ROOT / "DATA" / "DELINEATION_DATA"
OUT = ROOT / "RESULTS" / "viewer"
CLEAN = ROOT / "DATA" / "DELINEATION_CLEAN"
DELINEATIONS = CLEAN / "delineations.csv"
REPORT = ROOT / "RESULTS" / "build_clean_data_report.csv"
MARGIN = 12  # voxels around the frame
STRUCT = np.ones((3, 3, 3), bool)  # 26-connectivity: two voxels touching by a corner = same piece
ISOLATED_MM = 3  # fragment more than 3 mm from its main block = "isolated" (otherwise "detached")
MAX_FRAGS = 200  # fragments listed per delineation (the counts stay exact)
MAX_FAR = 50000  # voxels outside the frame sent to the page

# Order of DOCUMENTATION/given_documents/colors.md. The label <-> nucleus mapping
# is NOT confirmed: assumption label 1 = first nucleus of the list, etc.
NUCLEI = [
    ("LGN", "#40e0d0"),       # turquoise
    ("MGN", "#ff69b4"),       # pink
    ("Pulvinar", "#ffd700"),  # yellow
    ("AV", "#e32626"),        # red
    ("VA", "#2eb82e"),        # green
    ("VLA/VLP", "#2a6fdb"),   # blue
    ("VPL", "#8b5a2b"),       # brown
    ("MD", "#8e44ad"),        # purple
    ("CM", "#ff8c00"),        # orange
]


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode("ascii")


def safe(subject):
    return subject.replace("?", "X")


def read_rows(path):
    """Rows of a CSV; empty (with a warning) if the file is missing."""
    if not path.exists():
        print(f"⚠ {path.relative_to(ROOT)} missing: run build_clean_data.py first")
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def list_files():
    """Delineations to show: every file of DELINEATION_CLEAN (clean / fixed) and every raw file
    that build_clean_data.py did not copy (excluded), with status, reason, subject and session."""
    report = read_rows(REPORT)
    fixes, excluded = defaultdict(list), defaultdict(list)
    for r in report:
        if r["action"].startswith("not copied"):
            excluded[r["original_file"]].append(r["issue"])
        elif r["new_file"]:
            fixes[r["new_file"]].append(r["issue"])

    files = []
    for row in read_rows(DELINEATIONS):
        if not (ROOT / row["filepath"]).exists():
            continue  # deleted by fix_problems.py (e.g. wrong number of nuclei)
        done = fixes.get(row["filepath"], [])
        files.append({"path": ROOT / row["filepath"], "file": row["filepath"],
                      "group": row["raterID"].split("_")[0], "rater": row["raterID"],
                      "subject": f"{row['scantype']}_{row['delineationID']}", "session": row["session"],
                      "step": "fixed" if done else "clean", "reason": "; ".join(done)})
    for rel, issues in excluded.items():
        parts = Path(rel).parts
        scan = scan_key(parts[-1])  # 'SUBC001_ses1' -> subject 'C_001', session '1' ('?' if unreadable)
        subject, session = (f"{scan[3]}_{scan[4:7]}", scan.split("_ses")[1]) if scan else (None, None)
        files.append({"path": DATA / rel, "file": (DATA / rel).relative_to(ROOT).as_posix(),
                      "group": parts[0].strip().replace("Group ", ""),
                      "rater": parts[1].strip().replace("Rater ", ""),
                      "subject": subject, "session": session, "step": "excluded", "reason": "; ".join(issues)})
    return files


def gaps_of(pts, lo):
    """Empty slices between the first and the last occupied slice, on each axis."""
    out = []
    for a in range(3):
        vals = np.unique(pts[:, a])
        for i in np.nonzero(np.diff(vals) > 1)[0]:
            out.append([a, int(vals[i] + 1 + lo[a]), int(vals[i + 1] - 1 + lo[a])])
    return out


def controls(data):
    """Checks per label and per side. Each label is bilateral: one main block on the left,
    one on the right (side = centre of the piece relative to the left-right centre of the
    delineation; RAS: small x = left). Any other piece is a fragment.
    Returned coordinates: voxels of the original volume."""
    coords = np.argwhere(data)
    lo, hi = coords.min(0), coords.max(0) + 1
    crop = data[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    cx = coords[:, 0].mean() - lo[0]
    stats, gaps, frags = {}, [], []
    nfrag = [0, 0, 0, 0]  # isolated, detached, isolated voxels, detached voxels
    for l in np.unique(crop[crop != 0]):
        l = int(l)
        comp, n = ndimage.label(crop == l, STRUCT)
        pts = np.argwhere(comp)
        ids = comp[tuple(pts.T)] - 1
        sizes = np.bincount(ids, minlength=n)
        cents = np.zeros((n, 3))
        np.add.at(cents, ids, pts)
        cents /= sizes[:, None]
        side = np.where(cents[:, 0] < cx, "L", "R")
        stats[str(l)] = {}
        for s in ("L", "R"):
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
            # gaps: on the main block + nearby fragments (isolated ones are listed separately)
            gaps += [[l, s] + g for g in gaps_of(pts[keep], lo)]
    frags.sort(key=lambda f: (f[6] <= ISOLATED_MM, -f[2]))
    return {"stats": stats, "gaps": gaps, "frags": frags[:MAX_FRAGS], "nfrag": nfrag}


def build_subject(subject, files):
    vols, metas = [], []
    for f in files:
        _, _, data = load(f["path"])
        labels = get_labels(data) if data is not None else None
        if not labels:
            continue  # unreadable, MRI instead of a mask, empty
        data = np.rint(data).astype(np.int64)
        vols.append(data)
        metas.append({
            "rater": f["rater"], "group": f["group"].replace("Group ", ""),
            "session": f["session"], "file": f["file"], "labels": sorted(labels),
            "nvox": int(np.count_nonzero(data)), "step": f["step"], "reason": f["reason"],
            **controls(data),
        })
    if not vols:
        return None

    # Common frame = 0.1–99.9 % percentiles of the voxels of every delineation
    # (stray voxels far from the thalamus would otherwise stretch the frame).
    # Voxels outside the frame are sent separately: the page shows them in red
    # in the overview (whole volume).
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
        idx = (x + nx * (y + ny * z)).astype("<u4")  # flat index, x varies fastest
        lab = np.clip(crop[x, y, z], 0, 65535).astype("<u2")
        dels.append({**metas[i], "idx": b64(idx), "lab": b64(lab)})

    return {"subject": subject, "shape": list(shape),
            "bbox": {"x0": lo[0], "y0": lo[1], "z0": lo[2], "nx": nx, "ny": ny, "nz": nzz},
            "dels": dels}


def main(only):
    by_subject = defaultdict(list)
    for f in list_files():
        if f["subject"]:
            by_subject[f["subject"]].append(f)

    (OUT / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "index.html", OUT / "index.html")
    build_tables.main()  # CSV reader: RESULTS/viewer/tables.html

    index_path = OUT / "data" / "index.js"
    index = {}
    if index_path.exists() and only:  # partial update: keep the other subjects
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
        # (session, status) of each delineation: the page counts according to the chosen filter
        index[subject] = {"subject": subject, "file": name,
                          "dels": [[d["session"], d["step"]] for d in payload["dels"]]}
        print(f"{subject:8s} {len(payload['dels']):2d} delineations")

    nuclei = [{"label": i + 1, "name": n, "color": c} for i, (n, c) in enumerate(NUCLEI)]
    index_path.write_text(
        # VIEWER_BUILD: added to the URL of the subject files so that the browser
        # does not reuse an old cached version after a new build
        f"window.VIEWER_BUILD={int(time.time())};\n"
        f"window.VIEWER_PARAMS={json.dumps({'isolated_mm': ISOLATED_MM})};\n"
        "window.VIEWER_NUCLEI=" + json.dumps(nuclei) + ";\nwindow.VIEWER_INDEX="
        # "?_" subjects (letter C/G missing from the name) at the end of the list
        + json.dumps(sorted(index.values(), key=lambda s: ("?" in s["subject"], s["subject"])), indent=0) + ";",
        encoding="utf-8")
    print(f"\nOpen: {OUT / 'index.html'}")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
