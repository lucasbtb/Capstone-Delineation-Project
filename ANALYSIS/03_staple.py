"""
03_staple.py — Délinéation de référence par STAPLE pour chaque scan délinéé par 3 raters ou plus.

Entrée : DATA/CLEAN_DELINEATION (sortie de 02_easy_clean.py --apply), un masque par rater et par scan.

STAPLE (Warfield et al., 2004, version multi-labels) estime en même temps :
  - la délinéation « vraie » la plus probable (la référence), voxel par voxel ;
  - la fiabilité de chaque rater : matrice de confusion theta[label donné, vrai label].
Un rater peu fiable pèse donc moins dans la référence qu'un vote majoritaire simple.

Calcul limité à la boîte englobant tous les voxels non nuls des raters du scan (+ marge) :
hors de cette boîte tous les raters disent 0, la référence vaut 0.
STAPLE ne dépend que du vecteur de votes de chaque voxel : les voxels qui ont exactement les mêmes
votes (ex. tous les raters disent 5) sont regroupés et comptés une fois avec leur effectif.
Résultat identique, mais quelques milliers de « motifs » au lieu de ~400 000 voxels.

Les scans sont traités en parallèle (--workers). Chaque scan terminé est enregistré tout de suite
(référence + lignes des CSV) : si le script est interrompu, --resume reprend où il s'est arrêté.

Sorties :
  DATA/STAPLE/<SCAN>_staple.nii.gz   référence (labels 0-9), grille du 1er masque du scan
  RESULTS/03_staple_raters.csv       une ligne par masque : Dice vs référence, sensibilité / spécificité STAPLE
  RESULTS/03_staple_scans.csv        une ligne par scan : nb raters, convergence, volumes de la référence, accord
  RESULTS/03_staple_report.md        résumé chiffré (écrit à la fin)
Ne modifie jamais CLEAN_DELINEATION. Sans --resume, DATA/STAPLE et les CSV sont vidés puis recréés.

Usage : python ANALYSIS/03_staple.py                  # tout recalculer, 4 scans en parallèle
        python ANALYSIS/03_staple.py --workers 8      # plus de scans en parallèle (~300 Mo chacun)
        python ANALYSIS/03_staple.py --resume         # reprendre après une interruption
"""

import argparse
import csv
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import nibabel as nib
import numpy as np

from checks import EXPECTED_SHAPE, dice, load, scan_key

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "DATA" / "CLEAN_DELINEATION"
OUT_DATA = ROOT / "DATA" / "STAPLE"
RESULTS = ROOT / "RESULTS"
RATERS_CSV = RESULTS / "03_staple_raters.csv"
SCANS_CSV = RESULTS / "03_staple_scans.csv"
REPORT = RESULTS / "03_staple_report.md"

MIN_RATERS = 3
LABELS = range(1, 10)
MARGIN = 3               # voxels ajoutés autour de la boîte englobante
INIT_RELIABILITY = 0.99  # theta initial : probabilité de donner le bon label
MAX_ITER = 1000
TOL = 1e-6               # arrêt quand theta bouge de moins que ça
DEFAULT_WORKERS = min(4, os.cpu_count() or 1)

RATER_FIELDS = (["scan", "group", "rater", "file", "n_raters"]
                + [f"{m}_{k}" for k in LABELS for m in ("dice", "sens")]
                + ["dice_mean", "dice_thalamus", "spec_background", "volume_mm3"])
SCAN_FIELDS = (["scan", "n_raters", "raters", "iterations", "converged",
                "uncertain_fraction", "unanimous_fraction", "volume_mm3"]
               + [f"volume_{k}" for k in LABELS]
               + ["dice_mean_raters", "dice_min_raters", "worst_rater"])


# ================================================================ STAPLE multi-labels
def vote_patterns(D):
    """D : (R, N) votes. Regroupe les voxels aux votes identiques.
    Retourne (P (R, M) motifs distincts, counts (M,) nb de voxels par motif, inverse (N,) motif de chaque voxel)."""
    R = D.shape[0]
    if R <= 15 and D.max() < 16:  # code entier sur 4 bits par rater : np.unique 1D, rapide
        code = np.zeros(D.shape[1], dtype=np.int64)
        for j in range(R):
            code = (code << 4) | D[j]
        uniq, inverse, counts = np.unique(code, return_inverse=True, return_counts=True)
        P = np.stack([(uniq >> (4 * (R - 1 - j))) & 15 for j in range(R)]).astype(np.intp)
        return P, counts, inverse
    P, inverse, counts = np.unique(D, axis=1, return_inverse=True, return_counts=True)
    return P.astype(np.intp), counts, inverse.ravel()


def staple(P, counts, K, max_iter=MAX_ITER, tol=TOL):
    """P : (R, M) motifs de votes 0..K-1, counts : nb de voxels par motif.
    Retourne W (M, K) probabilité a posteriori de chaque vrai label par motif,
    theta (R, K, K) avec theta[j, donné, vrai], nb d'itérations, convergé ?"""
    R, M = P.shape
    eps = 1e-12
    c = counts.astype(np.float64)[:, None]
    onehot = np.eye(K)[P]  # (R, M, K), petit : M motifs, pas N voxels
    # a priori : fréquence globale de chaque label dans les votes (fixe, comme Warfield 2004)
    prior = (onehot * c).sum(axis=(0, 1)) / (R * counts.sum())
    log_prior = np.log(np.maximum(prior, eps))
    theta = np.full((R, K, K), (1 - INIT_RELIABILITY) / max(K - 1, 1))
    theta[:, np.arange(K), np.arange(K)] = INIT_RELIABILITY

    for it in range(1, max_iter + 1):
        # E : W[m, s] ∝ prior[s] · Π_j theta[j, P[j,m], s]
        log_theta = np.log(np.maximum(theta, eps))
        log_w = log_prior + sum(log_theta[j][P[j]] for j in range(R))
        log_w -= log_w.max(axis=1, keepdims=True)
        W = np.exp(log_w)
        W /= W.sum(axis=1, keepdims=True)
        # M : theta[j, s', s] = Σ_{voxels : vote j = s'} W[., s] / Σ_voxels W[., s]
        Wc = W * c
        new = np.einsum("rmk,ms->rks", onehot, Wc) / np.maximum(Wc.sum(axis=0), eps)
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
            {"file": path.relative_to(CLEAN).as_posix(), "path": path,
             "group": parts[0], "rater": parts[1].replace("Rater ", "")})
    return by_scan


def load_scan(entries):
    """Masques d'un scan (déjà validés par 02). Retourne (masques uint8, affine du 1er)."""
    masks, affine = [], None
    for e in entries:
        _, img, data = load(e["path"])
        if data is None or tuple(data.shape) != EXPECTED_SHAPE:
            raise ValueError(f"masque illisible ou mauvaise grille : {e['file']}  (relancer 02_easy_clean.py --apply)")
        if affine is None:
            affine = img.affine
        masks.append(np.round(data).astype(np.uint8))
        del data, img
    return masks, affine


# ================================================================ calcul d'un scan
def bounding_box(masks):
    fg = np.zeros(EXPECTED_SHAPE, dtype=bool)
    for m in masks:
        fg |= m > 0
    idx = np.argwhere(fg)
    lo = np.maximum(idx.min(axis=0) - MARGIN, 0)
    hi = np.minimum(idx.max(axis=0) + MARGIN + 1, fg.shape)
    return tuple(slice(a, b) for a, b in zip(lo, hi))


def run_scan(masks):
    """STAPLE sur un scan. Retourne la référence (volume entier), les infos par rater et par scan."""
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

    # mêmes statistiques qu'avant, calculées sur les motifs pondérés par leur effectif
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
    """Exécuté dans un processus séparé : calcule un scan et écrit sa référence.
    Retourne (scan, lignes raters, ligne scan, secondes)."""
    t0 = time.time()
    masks, affine = load_scan(entries)
    reference, raters, info = run_scan(masks)
    tmp = OUT_DATA / f"{scan}_staple.part.nii.gz"  # écrit puis renommé : jamais de fichier à moitié écrit
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


# ================================================================ CSV (enregistrés au fur et à mesure)
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
    """Valeur lue dans un CSV -> nombre / booléen quand c'en est un."""
    if value in ("True", "False"):
        return value == "True"
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


# ================================================================ rapport
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


# ================================================================ programme principal
def main():
    parser = argparse.ArgumentParser(description="Références STAPLE pour chaque scan avec >= 3 raters.")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"scans calculés en parallèle (défaut {DEFAULT_WORKERS}, ~300 Mo de mémoire chacun)")
    parser.add_argument("--resume", action="store_true",
                        help="reprendre : garder les scans déjà enregistrés, calculer seulement les autres")
    args = parser.parse_args()

    if not CLEAN.exists():
        sys.exit(f"Dossier absent : {CLEAN}  (lancer 02_easy_clean.py --apply)")
    by_scan = collect()
    eligible = sorted(s for s in by_scan if len(by_scan[s]) >= MIN_RATERS)
    n_skipped = len(by_scan) - len(eligible)
    RESULTS.mkdir(exist_ok=True)

    rater_rows, scan_rows = [], []
    if args.resume:
        # un scan compte comme fait s'il a sa ligne dans 03_staple_scans.csv ET sa référence sur le disque
        scan_rows = [r for r in read_csv(SCANS_CSV) if r["scan"] in eligible
                     and (OUT_DATA / f"{r['scan']}_staple.nii.gz").exists()]
        done = {r["scan"] for r in scan_rows}
        rater_rows = [r for r in read_csv(RATERS_CSV) if r["scan"] in done]
        OUT_DATA.mkdir(parents=True, exist_ok=True)
        for part in OUT_DATA.glob("*.part.nii.gz"):  # restes d'une écriture interrompue
            part.unlink()
    else:
        if OUT_DATA.exists():
            assert OUT_DATA.name == "STAPLE" and OUT_DATA.parent.name == "DATA"
            shutil.rmtree(OUT_DATA)  # dossier généré : recréé à chaque exécution
        OUT_DATA.mkdir(parents=True)
        done = set()
    write_csv(rater_rows, RATERS_CSV, RATER_FIELDS)  # en-tête + lignes déjà faites ; la suite est ajoutée
    write_csv(scan_rows, SCANS_CSV, SCAN_FIELDS)

    todo = [s for s in eligible if s not in done]
    print(f"{len(eligible)} scans avec >= {MIN_RATERS} raters : {len(done)} déjà faits, {len(todo)} à calculer "
          f"({args.workers} en parallèle)")
    t0 = time.time()
    try:
        with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {pool.submit(process_scan, s, by_scan[s]): s for s in todo}
            for k, fut in enumerate(as_completed(futures), 1):
                scan, rows, row, secs = fut.result()
                append_csv(rows, RATERS_CSV, RATER_FIELDS)  # enregistré tout de suite : rien de perdu si arrêt
                append_csv([row], SCANS_CSV, SCAN_FIELDS)
                rater_rows += rows
                scan_rows.append(row)
                print(f"  [{k:3d}/{len(todo)}] {scan}  {row['n_raters']} raters  {row['iterations']:4d} it"
                      f"{'' if row['converged'] else ' (NON CONVERGÉ)'}  Dice moyen {row['dice_mean_raters']:.3f}"
                      f"  {secs:.1f} s")
    except BrokenProcessPool:
        sys.exit("\nUn processus de calcul a été tué (manque de mémoire ?). Les scans terminés sont enregistrés :\n"
                 "relancer avec  python ANALYSIS/03_staple.py --resume --workers 2")
    except KeyboardInterrupt:
        sys.exit("\nInterrompu. Les scans terminés sont enregistrés : relancer avec --resume.")

    # CSV finaux triés par scan, puis rapport
    rater_rows.sort(key=lambda r: (r["scan"], r["rater"]))
    scan_rows.sort(key=lambda r: r["scan"])
    write_csv(rater_rows, RATERS_CSV, RATER_FIELDS)
    write_csv(scan_rows, SCANS_CSV, SCAN_FIELDS)
    REPORT.write_text(report(rater_rows, scan_rows, n_skipped), encoding="utf-8")
    print(f"\n{len(scan_rows)} références dans {OUT_DATA.relative_to(ROOT)}/ en {time.time() - t0:.0f} s "
          f"({n_skipped} scans avec moins de {MIN_RATERS} raters)")
    print(f"Rapport : {REPORT.relative_to(ROOT)} (+ {RATERS_CSV.name}, {SCANS_CSV.name})")


if __name__ == "__main__":
    main()
