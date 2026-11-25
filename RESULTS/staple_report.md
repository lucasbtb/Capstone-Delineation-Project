# STAPLE: reference delineations

Scans of DELINEATION_CLEAN with at least 3 raters (31 scans have fewer). Dice = agreement of a rater with the STAPLE reference of the same scan; values: median [Q1–Q3].

**Problems of fix_problems.py when this ran:** nuclei: fixed, 25 flagged; lr_flip: not run; stray_points: not run; incomplete: not run; swapped_labels: not run; far_points: not run; stopped_halfway: not run; missing_frames: not run; shifted_scan: not run.

## Overview

| | value |
|---|---|
| scans | 78 |
| masks used | 331 |
| raters per scan | 4 [3–5] |
| not converged | 3 |
| mean Dice 1–9 (per mask) | 0.771 [0.670–0.822] |
| whole-thalamus Dice | 0.882 [0.847–0.905] |
| masks with mean Dice < 0.5 | 14 |
| unanimous voxels (thalamus) | 0.337 [0.263–0.422] |
| uncertain voxels (prob < 0.9) | 0.060 [0.036–0.113] |
| reference volume (mm³) | 9316 [8485–10212] |

## Agreement per nucleus

| nucleus | Dice rater vs reference | STAPLE sensitivity | reference volume (mm³) |
|---|---|---|---|
| 1 | 0.784 [0.715–0.839] | 0.708 [0.602–0.800] | 306 [262–352] |
| 2 | 0.778 [0.723–0.828] | 0.709 [0.622–0.786] | 757 [629–861] |
| 3 | 0.849 [0.782–0.883] | 0.799 [0.693–0.867] | 2234 [1997–2425] |
| 4 | 0.896 [0.868–0.919] | 0.865 [0.814–0.909] | 2986 [2692–3244] |
| 5 | 0.788 [0.707–0.835] | 0.709 [0.612–0.802] | 230 [187–278] |
| 6 | 0.774 [0.692–0.857] | 0.701 [0.586–0.820] | 160 [136–187] |
| 7 | 0.625 [0.407–0.753] | 0.493 [0.290–0.646] | 355 [300–405] |
| 8 | 0.878 [0.814–0.907] | 0.842 [0.757–0.895] | 1569 [1422–1738] |
| 9 | 0.748 [0.547–0.809] | 0.661 [0.443–0.759] | 724 [666–804] |

## Scans with the least agreement

| scan | raters | mean Dice | min Dice (rater) | uncertain voxels |
|---|---|---|---|---|
| C_017_1 | 3 | 0.511 | 0.000 (16_2) | 0.077 |
| C_009_1 | 3 | 0.586 | 0.030 (9_1) | 0.130 |
| C_022_2 | 6 | 0.600 | 0.419 (10_5) | 0.088 |
| C_003_2 | 9 | 0.630 | 0.027 (16_2) | 0.056 |
| C_004_2 | 8 | 0.632 | 0.032 (16_2) | 0.041 |
| C_001_2 | 5 | 0.640 | 0.000 (1_1) | 0.043 |
| C_002_2 | 5 | 0.659 | 0.100 (16_2) | 0.088 |
| C_041_2 | 4 | 0.668 | 0.577 (13_1) | 0.085 |
| G_008_1 | 6 | 0.672 | 0.552 (14_2) | 0.030 |
| C_030_2 | 6 | 0.677 | 0.494 (11_3) | 0.047 |

## Masks with the least agreement with the reference

| scan | rater | mean Dice 1–9 | thalamus Dice | weakest nucleus |
|---|---|---|---|---|
| C_001_2 | 1_1 | 0.000 | 0.018 | 1 (0.000) |
| C_017_1 | 16_2 | 0.000 | 0.068 | 1 (0.000) |
| C_003_2 | 16_2 | 0.027 | 0.233 | 1 (0.000) |
| C_009_1 | 9_1 | 0.030 | 0.313 | 1 (0.000) |
| C_004_2 | 16_2 | 0.032 | 0.195 | 1 (0.000) |
| C_002_2 | 16_2 | 0.100 | 0.337 | 7 (0.000) |
| C_022_2 | 10_5 | 0.419 | 0.865 | 8 (0.000) |
| G_007_1 | 13_2 | 0.444 | 0.912 | 5 (0.000) |
| C_025_2 | 10_2 | 0.474 | 0.867 | 8 (0.000) |
| C_028_2 | 11_3 | 0.478 | 0.768 | 9 (0.000) |
| C_030_2 | 11_3 | 0.494 | 0.765 | 9 (0.000) |
| C_055_2 | 14_2 | 0.495 | 0.813 | 9 (0.000) |
| C_051_1 | 7_5 | 0.497 | 0.788 | 9 (0.000) |
| C_049_1 | 7_5 | 0.498 | 0.755 | 9 (0.000) |
| C_049_2 | 14_2 | 0.501 | 0.833 | 7 (0.000) |

Detail per mask: `staple_report_raters.csv`; per scan: `staple_report_scans.csv`.
