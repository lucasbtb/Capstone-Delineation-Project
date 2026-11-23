"""
build_viewer.py — Prepares the local website for comparing the delineations of DATA/DELINEATION_CLEAN.

Only shows the clean data, i.e. the output of the analysis (build_clean_data.py, then fix_problems.py,
then optionally staple.py). One page per scan (C|G ID + session, e.g. C_001_1), with:
  - every delineation listed in DATA/DELINEATION_CLEAN/delineations.csv for that scan, with the
    <problem>_flag / <problem>_fix columns written by fix_problems.py (a problem without columns = not run);
  - the delineations whose file fix_problems.py deleted: listed, red-flagged with the reason, not drawable
    (their file no longer exists);
  - the STAPLE reference DATA/STAPLE/<scan>_staple.nii.gz (staple.py), as an extra layer, when it exists.
Raw files of DATA/DELINEATION_DATA are never read.

Keeps only the non-zero voxels inside the scan's common bounding box, and writes:
  RESULTS/viewer/index.html          (copy of ANALYSIS/viewer/index.html)
  RESULTS/viewer/data/index.js       (list of scans)
  RESULTS/viewer/data/<SCAN>.js      (masks of the scan, base64-encoded)
Also computes exploratory checks (help to detect problems not handled by fix_problems.py yet):
  volume of each label per side (L/R), fragments (pieces separate from the main block),
  gaps between slices, voxels outside the displayed frame.
Rerun this script after build_clean_data.py / fix_problems.py / staple.py.

Then open RESULTS/viewer/index.html in a browser (no server, no data sent online).
Does not modify any file of DATA/.

Usage: python ANALYSIS/viewer/build_viewer.py [SCAN|SUBJECT ...]
       (e.g. C_001_1, or C_001 for both sessions; no argument = every scan)
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
sys.path.insert(0, str(HERE.parent))  # helpers.py and fix_problems.py are in ANALYSIS/
from helpers import get_labels, load  # noqa: E402
from fix_problems import PROBLEMS  # noqa: E402  (names and order of the problems)
import build_tables  # noqa: E402  (same folder as this script)

ROOT = HERE.parents[1]
OUT = ROOT / "RESULTS" / "viewer"
CLEAN = ROOT / "DATA" / "DELINEATION_CLEAN"
DELINEATIONS = CLEAN / "delineations.csv"
STAPLE = ROOT / "DATA" / "STAPLE"
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


def problems_of(row):
    """[name, flag, fix] for every problem of fix_problems.py, in order.
    flag = True / False, or None when the problem has not been run (no column, or empty cell)."""
    out = []
    for name in PROBLEMS:
        flag = row.get(f"{name}_flag", "")
        out.append([name, None if flag == "" else flag == "True", row.get(f"{name}_fix", "")])
    return out


def list_scans():
    """{scan: [delineation, ...]} from delineations.csv, plus the STAPLE reference of each scan if it exists."""
    if not DELINEATIONS.exists():
        print(f"⚠ {DELINEATIONS.relative_to(ROOT)} missing: run build_clean_data.py (then fix_problems.py) first")
        return {}
    with open(DELINEATIONS, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    scans = defaultdict(list)
    for row in rows:
        scan = f"{row['scantype']}_{row['delineationID']}_{row['session']}"
        path = ROOT / row["filepath"]
        scans[scan].append({"path": path, "file": row["filepath"], "kind": "rater", "deleted": not path.exists(),
                            "rater": row["raterID"], "group": row["raterID"].split("_")[0],
                            "problems": problems_of(row)})
    for scan, files in scans.items():
        ref = STAPLE / f"{scan}_staple.nii.gz"
        if ref.exists():
            files.append({"path": ref, "file": ref.relative_to(ROOT).as_posix(), "kind": "staple", "deleted": False,
                          "rater": "STAPLE", "group": "", "problems": []})
    return scans


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


def build_scan(scan, files):
    vols, metas, deleted = [], [], []
    for f in files:
        meta = {k: f[k] for k in ("file", "kind", "rater", "group", "problems")}
        if f["deleted"]:  # deleted by fix_problems.py: listed with its reason, nothing to draw
            deleted.append({**meta, "deleted": True})
            continue
        _, _, data = load(f["path"])
        labels = get_labels(data) if data is not None else None
        if not labels:
            print(f"   ⚠ {f['file']}: unreadable or empty, skipped")
            continue
        data = np.rint(data).astype(np.int64)
        vols.append(data)
        metas.append({**meta, "deleted": False, "labels": sorted(labels),
                      "nvox": int(np.count_nonzero(data)), **controls(data)})
    if not vols:  # every delineation of the scan was deleted: list them, nothing to draw
        return {"scan": scan, "shape": None, "bbox": None, "problems": list(PROBLEMS),
                "dels": sorted(deleted, key=lambda m: (m["group"].zfill(2), m["rater"]))} if deleted else None

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

    # order: STAPLE reference first, then the raters (group, rater), the deleted ones at their place
    key = lambda m: (m["kind"] != "staple", m["group"].zfill(2), m["rater"])
    drawn = []
    for i in sorted(range(len(vols)), key=lambda i: key(metas[i])):
        crop = vols[i][lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
        x, y, z = np.nonzero(crop)
        idx = (x + nx * (y + ny * z)).astype("<u4")  # flat index, x varies fastest
        lab = np.clip(crop[x, y, z], 0, 65535).astype("<u2")
        drawn.append({**metas[i], "idx": b64(idx), "lab": b64(lab)})
    dels = sorted(drawn + deleted, key=key)

    return {"scan": scan, "shape": list(shape),
            "bbox": {"x0": lo[0], "y0": lo[1], "z0": lo[2], "nx": nx, "ny": ny, "nz": nzz},
            "problems": list(PROBLEMS), "dels": dels}


def main(only):
    scans = list_scans()
    data_dir = OUT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "index.html", OUT / "index.html")
    build_tables.main()  # CSV reader: RESULTS/viewer/tables.html

    index_path = data_dir / "index.js"
    index = {}
    if index_path.exists() and only:  # partial update: keep the other scans
        txt = index_path.read_text(encoding="utf-8")
        txt = txt[txt.index("window.VIEWER_INDEX=") + len("window.VIEWER_INDEX="):].rstrip().rstrip(";")
        index = {s["scan"]: s for s in json.loads(txt) if "scan" in s}
    if not only:  # full build: remove the data files of scans (or of an older version) no longer shown
        for p in data_dir.glob("*.js"):
            if p.name not in ("index.js", "tables.js"):
                p.unlink()

    for scan in sorted(scans):
        if only and scan not in only and scan.rsplit("_", 1)[0] not in only:
            continue
        payload = build_scan(scan, scans[scan])
        if payload is None:
            index.pop(scan, None)
            (data_dir / f"{scan}.js").unlink(missing_ok=True)
            continue
        (data_dir / f"{scan}.js").write_text(
            f"window.VIEWER_DATA=window.VIEWER_DATA||{{}};window.VIEWER_DATA[{json.dumps(scan)}]="
            + json.dumps(payload, separators=(",", ":")) + ";", encoding="utf-8")
        raters = [d for d in payload["dels"] if d["kind"] == "rater"]
        index[scan] = {"scan": scan, "file": scan,
                       "n": sum(not d["deleted"] for d in raters), "ndeleted": sum(d["deleted"] for d in raters),
                       "staple": any(d["kind"] == "staple" for d in payload["dels"])}
        e = index[scan]
        print(f"{scan:9s} {e['n']:2d} delineations" + (f", {e['ndeleted']} deleted" if e["ndeleted"] else "")
              + (" + STAPLE" if e["staple"] else ""))

    nuclei = [{"label": i + 1, "name": n, "color": c} for i, (n, c) in enumerate(NUCLEI)]
    index_path.write_text(
        # VIEWER_BUILD: added to the URL of the scan files so that the browser
        # does not reuse an old cached version after a new build
        f"window.VIEWER_BUILD={int(time.time())};\n"
        f"window.VIEWER_PARAMS={json.dumps({'isolated_mm': ISOLATED_MM})};\n"
        "window.VIEWER_NUCLEI=" + json.dumps(nuclei) + ";\nwindow.VIEWER_INDEX="
        + json.dumps(sorted(index.values(), key=lambda s: s["scan"]), indent=0) + ";",
        encoding="utf-8")
    print(f"\nOpen: {OUT / 'index.html'}")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
