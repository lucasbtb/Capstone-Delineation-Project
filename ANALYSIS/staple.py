"""
staple.py — Reference delineation by STAPLE for each scan delineated by 3 raters or more.

Input: DATA/DELINEATION_CLEAN (output of build_clean_data.py, then fix_problems.py), one mask per rater
and per scan, listed in its delineations.csv. Rows whose file was deleted by fix_problems.py are skipped.
The report states which fix_problems.py problems had been run (from the <problem>_flag / _fix columns).

STAPLE (Warfield et al., 2004, multi-label version) estimates at the same time:
  - the most probable "true" delineation (the reference), voxel by voxel;
  - the reliability of each rater: confusion matrix theta[given label, true label].
An unreliable rater therefore weighs less in the reference than in a simple majority vote.

Computation limited to the box around all non-zero voxels of the scan's raters (+ margin):
outside this box every rater says 0, the reference is 0.
STAPLE only depends on the vote vector of each voxel: voxels with exactly the same votes
(e.g. every rater says 5) are grouped and counted once with their number of voxels.
Identical result, but a few thousand "patterns" instead of ~400,000 voxels.

Scans are processed in parallel (--workers). Each finished scan is saved immediately
(reference + CSV rows): if the script is interrupted, --resume continues where it stopped.

Outputs:
  DATA/STAPLE/<SCAN>_staple.nii.gz   reference (labels 0-9), grid of the scan's first mask
  RESULTS/staple_report.md           summary with statistics (written at the end)
  RESULTS/staple_report_raters.csv   one row per mask: Dice vs reference, STAPLE sensitivity / specificity
  RESULTS/staple_report_scans.csv    one row per scan: nb of raters, convergence, reference volumes, agreement
Never modifies DELINEATION_CLEAN. Without --resume, DATA/STAPLE and the CSVs are emptied and recreated.

Usage: python ANALYSIS/staple.py                  # recompute everything, 4 scans in parallel
       python ANALYSIS/staple.py --workers 8      # more scans in parallel (~300 MB each)
       python ANALYSIS/staple.py --resume         # continue after an interruption
"""

import argparse
import csv
import os
import shutil
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import nibabel as nib
import numpy as np

from helpers import EXPECTED_SHAPE, dice, load

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "DATA" / "DELINEATION_CLEAN"
OUT_DATA = ROOT / "DATA" / "STAPLE"
RESULTS = ROOT / "RESULTS"
RATERS_CSV = RESULTS / "staple_report_raters.csv"
SCANS_CSV = RESULTS / "staple_report_scans.csv"
REPORT = RESULTS / "staple_report.md"

MIN_RATERS = 3
LABELS = range(1, 10)
MARGIN = 3               # voxels added around the bounding box
INIT_RELIABILITY = 0.99  # initial theta: probability of giving the right label
MAX_ITER = 1000
TOL = 1e-6               # stop when theta moves less than this
DEFAULT_WORKERS = min(4, os.cpu_count() or 1)

RATER_FIELDS = (["scan", "group", "rater", "file", "n_raters"]
                + [f"{m}_{k}" for k in LABELS for m in ("dice", "sens")]
                + ["dice_mean", "dice_thalamus", "spec_background", "volume_mm3"])
SCAN_FIELDS = (["scan", "n_raters", "raters", "iterations", "converged",
                "uncertain_fraction", "unanimous_fraction", "volume_mm3"]
               + [f"volume_{k}" for k in LABELS]
               + ["dice_mean_raters", "dice_min_raters", "worst_rater"])


# ================================================================ multi-label STAPLE
def vote_patterns(D):
    """D: (R, N) votes. Groups the voxels with identical votes.
    Returns (P (R, M) distinct patterns, counts (M,) nb of voxels per pattern, inverse (N,) pattern of each voxel)."""
    R = D.shape[0]
    if R <= 15 and D.max() < 16:  # integer code, 4 bits per rater: 1D np.unique, fast
        code = np.zeros(D.shape[1], dtype=np.int64)
        for j in range(R):
            code = (code << 4) | D[j]
        uniq, inverse, counts = np.unique(code, return_inverse=True, return_counts=True)
        P = np.stack([(uniq >> (4 * (R - 1 - j))) & 15 for j in range(R)]).astype(np.intp)
        return P, counts, inverse
    P, inverse, counts = np.unique(D, axis=1, return_inverse=True, return_counts=True)
    return P.astype(np.intp), counts, inverse.ravel()


def staple(P, counts, K, max_iter=MAX_ITER, tol=TOL):
    """P: (R, M) vote patterns 0..K-1, counts: nb of voxels per pattern.
    Returns W (M, K) posterior probability of each true label per pattern,
    theta (R, K, K) with theta[j, given, true], nb of iterations, converged?"""
    R, M = P.shape
    eps = 1e-12
    c = counts.astype(np.float64)[:, None]
    onehot = np.eye(K)[P]  # (R, M, K), small: M patterns, not N voxels
    # prior: global frequency of each label in the votes (fixed, as in Warfield 2004)
    prior = (onehot * c).sum(axis=(0, 1)) / (R * counts.sum())
    log_prior = np.log(np.maximum(prior, eps))
    theta = np.full((R, K, K), (1 - INIT_RELIABILITY) / max(K - 1, 1))
    theta[:, np.arange(K), np.arange(K)] = INIT_RELIABILITY

    for it in range(1, max_iter + 1):
        # E: W[m, s] ∝ prior[s] · Π_j theta[j, P[j,m], s]
        log_theta = np.log(np.maximum(theta, eps))
        log_w = log_prior + sum(log_theta[j][P[j]] for j in range(R))
        log_w -= log_w.max(axis=1, keepdims=True)
        W = np.exp(log_w)
        W /= W.sum(axis=1, keepdims=True)
        # M: theta[j, s', s] = Σ_{voxels: vote j = s'} W[., s] / Σ_voxels W[., s]
        Wc = W * c
        new = np.einsum("rmk,ms->rks", onehot, Wc) / np.maximum(Wc.sum(axis=0), eps)
        delta = np.abs(new - theta).max()
        theta = new
        if delta < tol:
            return W, theta, it, True
    return W, theta, max_iter, False


# ================================================================ reading the masks
def collect():
    """Delineations of DELINEATION_CLEAN grouped by scan ('C_001_1'), read from its delineations.csv."""
    by_scan = defaultdict(list)
    with open(CLEAN / "delineations.csv", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not (ROOT / row["filepath"]).exists():
                continue  # deleted by fix_problems.py (e.g. wrong number of nuclei)
            scan = f"{row['scantype']}_{row['delineationID']}_{row['session']}"
            by_scan[scan].append({"file": row["filepath"], "path": ROOT / row["filepath"],
                                  "group": row["raterID"].split("_")[0], "rater": row["raterID"]})
    return by_scan


def problems_status():
    """One line on the fix_problems.py problems, read from the <problem>_flag / <problem>_fix columns of
    delineations.csv: not run, flagged only (no_changes) or fixed, with the number of delineations flagged."""
    from fix_problems import PROBLEMS  # names of every problem, in the order of the instructions
    with open(CLEAN / "delineations.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    parts = []
    for name in PROBLEMS:
        if not rows or f"{name}_flag" not in rows[0]:
            parts.append(f"{name}: not run")
            continue
        flagged = [r for r in rows if r[f"{name}_flag"] == "True"]
        flag_only = any(r[f"{name}_fix"].startswith("not fixed (no_changes)") for r in flagged)
        state = "flagged only (no_changes)" if flag_only else "fixed" if flagged else "run"
        parts.append(f"{name}: {state}, {len(flagged)} flagged")
    return "; ".join(parts)


def rater_key(rater):
    """'16_2' -> (16, 2), so that rater 2_1 comes before 10_1."""
    return tuple(int(x) for x in rater.split("_"))


def load_scan(entries):
    """Masks of one scan (already validated by build_clean_data.py). Returns (uint8 masks, affine of the first one)."""
    masks, affine = [], None
    for e in entries:
        _, img, data = load(e["path"])
        if data is None or tuple(data.shape) != EXPECTED_SHAPE:
            raise ValueError(f"unreadable mask or wrong grid: {e['file']}  (rerun build_clean_data.py)")
        if affine is None:
            affine = img.affine
        masks.append(np.round(data).astype(np.uint8))
        del data, img
    return masks, affine


# ================================================================ computing one scan
def bounding_box(masks):
    fg = np.zeros(EXPECTED_SHAPE, dtype=bool)
    for m in masks:
        fg |= m > 0
    idx = np.argwhere(fg)
    lo = np.maximum(idx.min(axis=0) - MARGIN, 0)
    hi = np.minimum(idx.max(axis=0) + MARGIN + 1, fg.shape)
    return tuple(slice(a, b) for a, b in zip(lo, hi))


def run_scan(masks):
    """STAPLE on one scan. Returns the reference (whole volume), the information per rater and per scan."""
    box = bounding_box(masks)
    D = np.stack([m[box].ravel() for m in masks])  # (R, N) uint8
    K = int(D.max()) + 1
    P, counts, inverse = vote_patterns(D)
    W, theta, n_iter, converged = staple(P, counts, K)
    ref_box = W.argmax(axis=1)[inverse]
    reference = np.zeros(EXPECTED_SHAPE, dtype=np.uint8)
    reference[box] = ref_box.reshape(reference[box].shape)

    raters = []
    for j in range(len(masks)):
        r = {}
        for k in LABELS:
            r[f"dice_{k}"] = round(float(dice(D[j] == k, ref_box == k)), 4)
            r[f"sens_{k}"] = round(float(theta[j, k, k]), 4) if k < K else ""
        r["dice_mean"] = round(float(np.nanmean([r[f"dice_{k}"] for k in LABELS])), 4)
        r["dice_thalamus"] = round(float(dice(D[j] > 0, ref_box > 0)), 4)
        r["spec_background"] = round(float(theta[j, 0, 0]), 6)
        r["volume_mm3"] = int((D[j] > 0).sum())
        raters.append(r)

    # statistics computed on the patterns, weighted by their number of voxels
    fg = (W.argmax(axis=1) > 0) | (P > 0).any(axis=0)
    n_fg = counts[fg].sum()
    scan = {"iterations": n_iter, "converged": converged,
            "uncertain_fraction": round(float(counts[fg & (W.max(axis=1) < 0.9)].sum() / n_fg), 4),
            "unanimous_fraction": round(float(counts[fg & (P == P[0]).all(axis=0)].sum() / n_fg), 4),
            "volume_mm3": int((ref_box > 0).sum())}
    for k in LABELS:
        scan[f"volume_{k}"] = int((ref_box == k).sum())
    return reference, raters, scan


def process_scan(scan, entries):
    """Run in a separate process: computes one scan and writes its reference.
    Returns (scan, rater rows, scan row, seconds)."""
    t0 = time.time()
    masks, affine = load_scan(entries)
    reference, raters, info = run_scan(masks)
    tmp = OUT_DATA / f"{scan}_staple.part.nii.gz"  # written then renamed: never a half-written file
    nib.save(nib.Nifti1Image(reference, affine), tmp)
    os.replace(tmp, OUT_DATA / f"{scan}_staple.nii.gz")
    rater_rows = [{"scan": scan, "group": e["group"], "rater": e["rater"], "file": e["file"],
                   "n_raters": len(masks), **r} for e, r in zip(entries, raters)]
    dices = [r["dice_mean"] for r in raters]
    scan_row = {"scan": scan, "n_raters": len(masks), "raters": " ".join(e["rater"] for e in entries), **info,
                "dice_mean_raters": round(float(np.mean(dices)), 4),
                "dice_min_raters": round(float(np.min(dices)), 4),
                "worst_rater": entries[int(np.argmin(dices))]["rater"]}
    return scan, rater_rows, scan_row, time.time() - t0


# ================================================================ CSV (saved as the scans finish)
def write_csv(rows, path, fields):
    tmp = path.with_suffix(".part")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def append_csv(rows, path, fields):
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=fields).writerows(rows)


def parse(value):
    """Value read from a CSV -> number / boolean when it is one."""
    if value in ("True", "False"):
        return value == "True"
    if "_" in value:  # rater IDs like '3_2': Python would read int('3_2') as 32
        return value
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            pass
    return value


def read_csv(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{k: parse(v) for k, v in row.items()} for row in csv.DictReader(f)]


# ================================================================ report
def q(values):
    """'median [Q1–Q3]' of a list of numbers."""
    v = np.array([x for x in values if x != "" and not np.isnan(x)], dtype=float)
    if not v.size:
        return "—"
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    fmt = ".0f" if np.all(v == np.round(v)) and v.max() > 1 else ".3f"  # counts / volumes as integers
    return f"{med:{fmt}} [{q1:{fmt}}–{q3:{fmt}}]"


def report(raters, scans, n_skipped, problems):
    L = ["# STAPLE: reference delineations", "",
         f"Scans of DELINEATION_CLEAN with at least {MIN_RATERS} raters ({n_skipped} scans have fewer). "
         "Dice = agreement of a rater with the STAPLE reference of the same scan; values: median [Q1–Q3].", "",
         f"**Problems of fix_problems.py when this ran:** {problems}.", "",
         "## Overview", "", "| | value |", "|---|---|"]
    lines = [
        ("scans", str(len(scans))),
        ("masks used", str(len(raters))),
        ("raters per scan", q([x["n_raters"] for x in scans])),
        ("not converged", str(sum(not x["converged"] for x in scans))),
        ("mean Dice 1–9 (per mask)", q([x["dice_mean"] for x in raters])),
        ("whole-thalamus Dice", q([x["dice_thalamus"] for x in raters])),
        ("masks with mean Dice < 0.5", str(sum(x["dice_mean"] < 0.5 for x in raters))),
        ("unanimous voxels (thalamus)", q([x["unanimous_fraction"] for x in scans])),
        ("uncertain voxels (prob < 0.9)", q([x["uncertain_fraction"] for x in scans])),
        ("reference volume (mm³)", q([x["volume_mm3"] for x in scans])),
    ]
    L += [f"| {label} | {value} |" for label, value in lines]

    L += ["", "## Agreement per nucleus", "",
          "| nucleus | Dice rater vs reference | STAPLE sensitivity | reference volume (mm³) |", "|---|---|---|---|"]
    for k in LABELS:
        L.append(f"| {k} | {q([x[f'dice_{k}'] for x in raters])} | {q([x[f'sens_{k}'] for x in raters])} | "
                 f"{q([x[f'volume_{k}'] for x in scans])} |")

    L += ["", "## Scans with the least agreement", "",
          "| scan | raters | mean Dice | min Dice (rater) | uncertain voxels |", "|---|---|---|---|---|"]
    for s in sorted(scans, key=lambda s: s["dice_mean_raters"])[:10]:
        L.append(f"| {s['scan']} | {s['n_raters']} | {s['dice_mean_raters']:.3f} | "
                 f"{s['dice_min_raters']:.3f} ({s['worst_rater']}) | {s['uncertain_fraction']:.3f} |")

    L += ["", "## Masks with the least agreement with the reference", "",
          "| scan | rater | mean Dice 1–9 | thalamus Dice | weakest nucleus |", "|---|---|---|---|---|"]
    for x in sorted(raters, key=lambda x: x["dice_mean"])[:15]:
        k = min(LABELS, key=lambda k: x[f"dice_{k}"] if not np.isnan(x[f"dice_{k}"]) else 2)
        L.append(f"| {x['scan']} | {x['rater']} | {x['dice_mean']:.3f} | {x['dice_thalamus']:.3f} | "
                 f"{k} ({x[f'dice_{k}']:.3f}) |")

    L += ["", "Detail per mask: `staple_report_raters.csv`; per scan: `staple_report_scans.csv`.", ""]
    return "\n".join(L)


# ================================================================ main program
def main():
    parser = argparse.ArgumentParser(description=f"STAPLE references for each scan with >= {MIN_RATERS} raters.")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"scans computed in parallel (default {DEFAULT_WORKERS}, ~300 MB of memory each)")
    parser.add_argument("--resume", action="store_true",
                        help="resume: keep the scans already saved, compute only the others")
    args = parser.parse_args()

    if not (CLEAN / "delineations.csv").exists():
        sys.exit(f"Missing {CLEAN / 'delineations.csv'}  (run build_clean_data.py)")
    by_scan = collect()
    eligible = sorted(s for s in by_scan if len(by_scan[s]) >= MIN_RATERS)
    n_skipped = len(by_scan) - len(eligible)
    RESULTS.mkdir(exist_ok=True)

    rater_rows, scan_rows = [], []
    if args.resume:
        # a scan counts as done if it has its row in staple_report_scans.csv AND its reference on disk
        scan_rows = [r for r in read_csv(SCANS_CSV) if r["scan"] in eligible
                     and (OUT_DATA / f"{r['scan']}_staple.nii.gz").exists()]
        done = {r["scan"] for r in scan_rows}
        rater_rows = [r for r in read_csv(RATERS_CSV) if r["scan"] in done]
        OUT_DATA.mkdir(parents=True, exist_ok=True)
        for part in OUT_DATA.glob("*.part.nii.gz"):  # leftovers of an interrupted write
            part.unlink()
    else:
        if OUT_DATA.exists():
            assert OUT_DATA.name == "STAPLE" and OUT_DATA.parent.name == "DATA"
            shutil.rmtree(OUT_DATA)  # generated folder: recreated on every run
        OUT_DATA.mkdir(parents=True)
        done = set()
    write_csv(rater_rows, RATERS_CSV, RATER_FIELDS)  # header + rows already done; the rest is appended
    write_csv(scan_rows, SCANS_CSV, SCAN_FIELDS)

    todo = [s for s in eligible if s not in done]
    print(f"{len(eligible)} scans with >= {MIN_RATERS} raters: {len(done)} already done, {len(todo)} to compute "
          f"({args.workers} in parallel)")
    t0 = time.time()
    try:
        with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {pool.submit(process_scan, s, by_scan[s]): s for s in todo}
            for k, fut in enumerate(as_completed(futures), 1):
                scan, rows, row, secs = fut.result()
                append_csv(rows, RATERS_CSV, RATER_FIELDS)  # saved immediately: nothing lost if stopped
                append_csv([row], SCANS_CSV, SCAN_FIELDS)
                rater_rows += rows
                scan_rows.append(row)
                print(f"  [{k:3d}/{len(todo)}] {scan}  {row['n_raters']} raters  {row['iterations']:4d} it"
                      f"{'' if row['converged'] else ' (NOT CONVERGED)'}  mean Dice {row['dice_mean_raters']:.3f}"
                      f"  {secs:.1f} s")
    except BrokenProcessPool:
        sys.exit("\nA worker process was killed (out of memory?). The finished scans are saved:\n"
                 "rerun with  python ANALYSIS/staple.py --resume --workers 2")
    except KeyboardInterrupt:
        sys.exit("\nInterrupted. The finished scans are saved: rerun with --resume.")

    # final CSVs sorted by scan, then the report
    rater_rows.sort(key=lambda r: (r["scan"], rater_key(r["rater"])))
    scan_rows.sort(key=lambda r: r["scan"])
    write_csv(rater_rows, RATERS_CSV, RATER_FIELDS)
    write_csv(scan_rows, SCANS_CSV, SCAN_FIELDS)
    REPORT.write_text(report(rater_rows, scan_rows, n_skipped, problems_status()), encoding="utf-8")
    print(f"\n{len(scan_rows)} references in {OUT_DATA.relative_to(ROOT)}/ in {time.time() - t0:.0f} s "
          f"({n_skipped} scans with fewer than {MIN_RATERS} raters)")
    print(f"Report: {REPORT.relative_to(ROOT)} (+ {RATERS_CSV.name}, {SCANS_CSV.name})")


if __name__ == "__main__":
    main()
