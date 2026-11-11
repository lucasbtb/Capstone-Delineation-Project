"""
03_staple.py — Délinéation de référence par STAPLE pour chaque scan délinéé par 3 raters ou plus.

Entrée : DATA/CLEAN_DELINEATION (sortie de 02_easy_clean.py --apply), un masque par rater et par scan.

STAPLE (Warfield et al., 2004, version multi-labels) estime en même temps :
  - la délinéation « vraie » la plus probable (la référence), voxel par voxel ;
  - la fiabilité de chaque rater : matrice de confusion theta[label donné, vrai label].
Un rater peu fiable pèse donc moins dans la référence qu'un vote majoritaire simple.

Calcul limité à la boîte englobant tous les voxels non nuls des raters du scan (+ marge) :
hors de cette boîte tous les raters disent 0, la référence vaut 0.

Sorties :
  DATA/STAPLE/<SCAN>_staple.nii.gz   référence (labels 0-9), grille du 1er masque du scan
  RESULTS/03_staple_raters.csv       une ligne par masque : Dice vs référence, sensibilité / spécificité STAPLE
  RESULTS/03_staple_scans.csv        une ligne par scan : nb raters, convergence, volumes de la référence, accord
  RESULTS/03_staple_report.md        résumé chiffré
Ne modifie jamais CLEAN_DELINEATION. DATA/STAPLE est vidé puis recréé.
Usage : python ANALYSIS/03_staple.py
"""

import csv
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import nibabel as nib
import numpy as np

from checks import EXPECTED_SHAPE, dice, load, scan_key

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "DATA" / "CLEAN_DELINEATION"
OUT_DATA = ROOT / "DATA" / "STAPLE"
RESULTS = ROOT / "RESULTS"

MIN_RATERS = 3
LABELS = range(1, 10)
MARGIN = 3               # voxels ajoutés autour de la boîte englobante
INIT_RELIABILITY = 0.99  # theta initial : probabilité de donner le bon label
MAX_ITER = 200
TOL = 1e-6               # arrêt quand theta bouge de moins que ça


# ================================================================ STAPLE multi-labels
def staple(D, max_iter=MAX_ITER, tol=TOL):
    """D : (R raters, N voxels) entiers 0..K-1.
    Retourne W (N, K) probabilité a posteriori de chaque vrai label,
    theta (R, K, K) avec theta[j, donné, vrai], nb d'itérations, convergé ?"""
    R, N = D.shape
    K = int(D.max()) + 1
    eps = 1e-12
    # a priori : fréquence globale de chaque label dans les votes (fixe, comme Warfield 2004)
    prior = np.bincount(D.ravel(), minlength=K) / D.size
    log_prior = np.log(np.maximum(prior, eps))
    theta = np.full((R, K, K), (1 - INIT_RELIABILITY) / max(K - 1, 1))
    theta[:, np.arange(K), np.arange(K)] = INIT_RELIABILITY
    onehot = np.eye(K, dtype=np.float64)[D]  # (R, N, K) : onehot[j, i, D[j,i]] = 1

    for it in range(1, max_iter + 1):
        # E : W[i, s] ∝ prior[s] · Π_j theta[j, D[j,i], s]
        log_w = np.tile(log_prior, (N, 1))
        for j in range(R):
            log_w += np.log(np.maximum(theta[j][D[j]], eps))
        log_w -= log_w.max(axis=1, keepdims=True)
        W = np.exp(log_w)
        W /= W.sum(axis=1, keepdims=True)
        # M : theta[j, s', s] = Σ_{i : D[j,i]=s'} W[i, s] / Σ_i W[i, s]
        total = np.maximum(W.sum(axis=0), eps)
        new = np.stack([onehot[j].T @ W for j in range(R)]) / total
        delta = np.abs(new - theta).max()
        theta = new
        if delta < tol:
            return W, theta, it, True
    return W, theta, max_iter, False


# ================================================================ lecture des masques
def collect():
    """Fichiers de CLEAN_DELINEATION groupés par scan ('SUBC001_ses01')."""
    by_scan = defaultdict(list)
    for path in sorted(p for p in CLEAN.rglob("*") if p.is_file()):
        parts = path.relative_to(CLEAN).parts
        m = re.fullmatch(r"SUB([CG])(\d{3})_ses([12])", scan_key(path.name) or "")
        if len(parts) < 3 or not m:
            sys.exit(f"Fichier inattendu dans CLEAN_DELINEATION : {path}  (relancer 02_easy_clean.py --apply)")
        by_scan[f"SUB{m.group(1)}{m.group(2)}_ses0{m.group(3)}"].append(
            {"file": str(path.relative_to(CLEAN)), "path": path,
             "group": parts[0], "rater": parts[1].replace("Rater ", "")})
    return by_scan


def load_scan(entries):
    """Masques d'un scan (déjà validés par 02). Retourne (masques uint8, affine du 1er)."""
    masks, affine = [], None
    for e in entries:
        _, img, data = load(e["path"])
        if data is None or tuple(data.shape) != EXPECTED_SHAPE:
            sys.exit(f"Masque illisible ou mauvaise grille : {e['file']}  (relancer 02_easy_clean.py --apply)")
        if affine is None:
            affine = img.affine
        masks.append(np.round(data).astype(np.uint8))
    return masks, affine


# ================================================================ statistiques
def bounding_box(masks):
    fg = np.any(np.stack([m > 0 for m in masks]), axis=0)
    idx = np.argwhere(fg)
    lo = np.maximum(idx.min(axis=0) - MARGIN, 0)
    hi = np.minimum(idx.max(axis=0) + MARGIN + 1, fg.shape)
    return tuple(slice(a, b) for a, b in zip(lo, hi))


def run_scan(masks):
    """STAPLE sur un scan. Retourne la référence (volume entier), les infos par rater et par scan."""
    box = bounding_box(masks)
    D = np.stack([m[box].ravel() for m in masks]).astype(np.int64)
    W, theta, n_iter, converged = staple(D)
    K = W.shape[1]
    ref_box = W.argmax(axis=1)
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

    confidence = W.max(axis=1)
    fg = (ref_box > 0) | (D > 0).any(axis=0)
    scan = {"iterations": n_iter, "converged": converged,
            "uncertain_fraction": round(float((confidence[fg] < 0.9).mean()), 4),
            "unanimous_fraction": round(float((D[:, fg] == D[0, fg]).all(axis=0).mean()), 4),
            "volume_mm3": int((ref_box > 0).sum())}
    for k in LABELS:
        scan[f"volume_{k}"] = int((ref_box == k).sum())
    return reference, raters, scan


# ================================================================ écriture
def write_csv(rows, path):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def q(values):
    """'médiane [Q1–Q3]' d'une liste de nombres."""
    v = np.array([x for x in values if x != "" and not np.isnan(x)], dtype=float)
    if not v.size:
        return "—"
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    fmt = ".0f" if np.all(v == np.round(v)) and v.max() > 1 else ".3f"  # comptes / volumes en entiers
    return f"{med:{fmt}} [{q1:{fmt}}–{q3:{fmt}}]"


def report(raters, scans, n_skipped):
    L = ["# 03 — STAPLE : délinéations de référence", "",
         f"Scans de CLEAN_DELINEATION avec au moins {MIN_RATERS} raters ({n_skipped} scans en ont moins). "
         "Dice = accord d'un rater avec la référence STAPLE du même scan ; valeurs : médiane [Q1–Q3].", "",
         "## Vue d'ensemble", "", "| | valeur |", "|---|---|"]
    lines = [
        ("scans", str(len(scans))),
        ("masques utilisés", str(len(raters))),
        ("raters par scan", q([x["n_raters"] for x in scans])),
        ("non convergés", str(sum(not x["converged"] for x in scans))),
        ("Dice moyen 1–9 (par masque)", q([x["dice_mean"] for x in raters])),
        ("Dice thalamus entier", q([x["dice_thalamus"] for x in raters])),
        ("masques Dice moyen < 0.5", str(sum(x["dice_mean"] < 0.5 for x in raters))),
        ("voxels unanimes (thalamus)", q([x["unanimous_fraction"] for x in scans])),
        ("voxels incertains (proba < 0.9)", q([x["uncertain_fraction"] for x in scans])),
        ("volume référence (mm³)", q([x["volume_mm3"] for x in scans])),
    ]
    L += [f"| {label} | {value} |" for label, value in lines]

    L += ["", "## Accord par noyau", "",
          "| noyau | Dice rater vs référence | sensibilité STAPLE | volume référence (mm³) |", "|---|---|---|---|"]
    for k in LABELS:
        L.append(f"| {k} | {q([x[f'dice_{k}'] for x in raters])} | {q([x[f'sens_{k}'] for x in raters])} | "
                 f"{q([x[f'volume_{k}'] for x in scans])} |")

    L += ["", "## Scans avec le moins d'accord", "",
          "| scan | raters | Dice moyen | Dice min (rater) | voxels incertains |", "|---|---|---|---|---|"]
    for s in sorted(scans, key=lambda s: s["dice_mean_raters"])[:10]:
        L.append(f"| {s['scan']} | {s['n_raters']} | {s['dice_mean_raters']:.3f} | "
                 f"{s['dice_min_raters']:.3f} ({s['worst_rater']}) | {s['uncertain_fraction']:.3f} |")

    L += ["", "## Masques les moins en accord avec la référence", "",
          "| scan | rater | Dice moyen 1–9 | Dice thalamus | noyau le plus faible |", "|---|---|---|---|---|"]
    for x in sorted(raters, key=lambda x: x["dice_mean"])[:15]:
        k = min(LABELS, key=lambda k: x[f"dice_{k}"] if not np.isnan(x[f"dice_{k}"]) else 2)
        L.append(f"| {x['scan']} | {x['rater']} | {x['dice_mean']:.3f} | {x['dice_thalamus']:.3f} | "
                 f"{k} ({x[f'dice_{k}']:.3f}) |")

    L += ["", "Détail par masque : `03_staple_raters.csv` ; par scan : `03_staple_scans.csv`.", ""]
    return "\n".join(L)


def main():
    if not CLEAN.exists():
        sys.exit(f"Dossier absent : {CLEAN}  (lancer 02_easy_clean.py --apply)")
    if OUT_DATA.exists():
        assert OUT_DATA.name == "STAPLE" and OUT_DATA.parent.name == "DATA"
        shutil.rmtree(OUT_DATA)  # dossier généré : recréé à chaque exécution
    OUT_DATA.mkdir(parents=True)

    by_scan = collect()
    rater_rows, scan_rows = [], []
    for scan in sorted(by_scan):
        entries = by_scan[scan]
        if len(entries) < MIN_RATERS:
            continue
        masks, affine = load_scan(entries)
        reference, raters, info = run_scan(masks)
        nib.save(nib.Nifti1Image(reference, affine), OUT_DATA / f"{scan}_staple.nii.gz")
        for e, r in zip(entries, raters):
            rater_rows.append({"scan": scan, "group": e["group"], "rater": e["rater"],
                               "file": e["file"], "n_raters": len(masks), **r})
        dices = [r["dice_mean"] for r in raters]
        scan_rows.append({"scan": scan, "n_raters": len(masks),
                          "raters": " ".join(e["rater"] for e in entries), **info,
                          "dice_mean_raters": round(float(np.mean(dices)), 4),
                          "dice_min_raters": round(float(np.min(dices)), 4),
                          "worst_rater": entries[int(np.argmin(dices))]["rater"]})
        print(f"  {scan}  {len(masks)} raters  {info['iterations']:3d} it"
              f"{'' if info['converged'] else ' (NON CONVERGÉ)'}  Dice moyen {np.mean(dices):.3f}")

    n_skipped = len(by_scan) - len(scan_rows)
    RESULTS.mkdir(exist_ok=True)
    write_csv(rater_rows, RESULTS / "03_staple_raters.csv")
    write_csv(scan_rows, RESULTS / "03_staple_scans.csv")
    (RESULTS / "03_staple_report.md").write_text(report(rater_rows, scan_rows, n_skipped), encoding="utf-8")
    print(f"\n{len(scan_rows)} références dans {OUT_DATA.relative_to(ROOT)}/ "
          f"({n_skipped} scans avec moins de {MIN_RATERS} raters)")
    print("Rapport : RESULTS/03_staple_report.md (+ 03_staple_raters.csv, 03_staple_scans.csv)")


if __name__ == "__main__":
    main()
