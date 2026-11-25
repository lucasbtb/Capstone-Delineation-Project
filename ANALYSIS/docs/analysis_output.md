# Analysis output

How the instructions of `analysis_instructions.md` were implemented in `ANALYSIS/`, what is still open,
and what to worry about. This file follows the sections of the instructions.

## Overview

```
DATA/DELINEATION_DATA  (raw, from the Google Drive, never modified)
        │
        └── build_clean_data.py ──► DATA/DELINEATION_CLEAN/<scan>/<scan>_<rater>.nii.gz + delineations.csv
                                  └─► RESULTS/build_clean_data_report.csv
                                          │
            fix_problems.py  ── flags / fixes IN PLACE, adds <problem>_flag / <problem>_fix to delineations.csv
                                          │
            staple.py ◄───────────────────┤  ──► DATA/STAPLE              (reference delineations)
                                          │   └─► RESULTS/staple_report.md + staple_report_*.csv
                                          │
            viewer/build_viewer.py ◄──────┘  ──► RESULTS/viewer/index.html (visual comparison, clean data only:
                    ▲                             delineations.csv + problem columns + DATA/STAPLE)
                    └──────────── DATA/STAPLE

delineation_explorer/   opens any .nii / .nii.gz in a local page (independent of the pipeline)
```

| File | Role |
|---|---|
| `build_clean_data.py` | Initial problems: cleans and reorganises the raw delineations (~7 s) |
| `staple.py` | STAPLE reference delineation per scan (~10 s) |
| `explore_delineations.ipynb` | Notebook summarising `delineations.csv` with charts: delineations by type and session, raters per scan (STAPLE threshold), sessions per subject, per group / rater, problems flagged, what the cleaning did. Read-only |
| `helpers.py` | Shared helpers: reading files whatever their format, reading names, Dice, reorientation |
| `fix_problems.py` | Further problems: one function per problem, flags each delineation and fixes it in place (~3 min, mostly `stray_points`) |
| `viewer/` | Web page comparing the raters of a scan with each other and with the STAPLE reference, showing the `fix_problems.py` flags; plus a CSV reader (`docs/viewer.md`) |
| `delineation_explorer/` | Web page to open any delineation files (`delineation_explorer/delineation_explorer.md`) |

Run order:

```
pip install -r requirements.txt                 # once
python ANALYSIS/build_clean_data.py             # DATA/DELINEATION_CLEAN + delineations.csv, RESULTS/build_clean_data_report.csv
python ANALYSIS/fix_problems.py                 # flag + fix the further problems (--no-changes: flag only)
python ANALYSIS/staple.py                       # STAPLE references, 4 scans in parallel (--workers N, --resume)
python ANALYSIS/viewer/build_viewer.py          # then open RESULTS/viewer/index.html
```

Every script rebuilds its outputs from scratch: rerun the later steps after changing an earlier one.

---

## Initial problems and `build_clean_data.py`

### How each listed problem is handled

| Problem (instructions) | How `build_clean_data.py` handles it | On the current data |
|---|---|---|
| **1. Files not named correctly** | Subject (C/G + ID) and session read from the name, tolerating `SUBCO29`, `SUBC20`, `ses01`, `Session 2`…; known mistakes fixed by hand in `NAME_FIXES`: 9b `ses9` → 1, 6j every file → ses1, 5f `SUBJEC35–37` → C, 5a `Sub 32- Final` → C, ses1, 8b `SUB008` → C. File type read from the **content**, not the extension: NIfTI files with a misleading name (`.nii`, `.nii.gz.gz`, `.zip`, uncompressed `.nii.gz`) are rewritten as real `.nii.gz`; non-NIfTI files are not copied | 13 names corrected, 35 files converted, 2 non-NIfTI files not copied (`.docx`, `.DS_Store`); every file can now be placed |
| **2. Duplicate files** (same rater, same scan) | Compared by voxel content. Exact copies → one kept (the real `.nii.gz` first). Different content → the **most recently modified** file is kept (earlier ones were unfinished saves) | 13 exact copies and 2 older versions (rater 15a) not copied |
| **3. Files are scans, not delineations** | A file with non-integer values is an MRI, not a mask → not copied | 15 MRIs not copied (raters 7d, 10j, 11e, 13f, 15g) |
| **4. Not sure the axis is always correct** | The header must be RAS (axis 0 → right, 1 → anterior, 2 → superior) on a 192×224×224 grid at 1 mm. A non-RAS header is reoriented to RAS (same voxels, stored in RAS order); a grid still wrong after that → not copied | Every file is already RAS on the right grid: nothing reoriented |

### The "Solution" section, point by point

| Instruction | Implementation |
|---|---|
| Takes the Google Drive structure in `DELINEATION_DATA` | Reads `DATA/DELINEATION_DATA/Group N/Rater Nx/…` (never modified) |
| Makes a `DELINEATION_CLEAN` folder | `DATA/DELINEATION_CLEAN/`, emptied and recreated on every run |
| One folder per scan (C/G ID + session) | e.g. `C_001_1/` = subject C 001, session 1 (110 scans) |
| Renamed `{G\|C}_<ID>_{1\|2}_<ratergroup>_<raterid>` | e.g. `C_001_1_3_2.nii.gz` = rater 2 of group 3 |
| Raters with no delineation removed, the others renumbered | Empty rater folders removed (86); within each group the remaining raters are numbered 1, 2, 3… in their original letter order (Group 3 with 3a empty, 3b, 3d → `3_1`, `3_2`) |
| Dataframe `index, filepath, scantype, delineationID, session, raterID` | `DATA/DELINEATION_CLEAN/delineations.csv` (408 rows) |
| Unclear files are renamed | See problem 1 and `NAME_FIXES` |
| Duplicates are handled | See problem 2 |

Extra output, not in the instructions: `RESULTS/build_clean_data_report.csv`, the log of everything the cleaning
did. One row per raw file and issue: `original_file, issue, action, new_file`. `action` is "not copied…" or what
was done (converted, reoriented, placed with the corrected name); `new_file` is the delineation it became.
A delineation with no row was copied unchanged. The viewer no longer reads it (it only shows the clean data);
it stays readable in the viewer's CSV reader.

Current result: **408 delineations from 440 raw files, 110 scans, 67 subjects, 81 raters.**

---

## Further problems and `fix_problems.py`

Works on `DATA/DELINEATION_CLEAN` and its `delineations.csv`.

### Architecture, point by point

| Instruction | Implementation |
|---|---|
| One function per problem in `fix_problems.py` | 9 functions, one per listed problem, all `problem(d, no_changes=False) -> (flag, fix)` |
| Iterates over all the delineations in `delineations.csv` | `run_problem(name, table)` calls the function on every row (skipping files already deleted by an earlier fix) |
| Adds `<problem>_flag` and `<problem>_fix` columns | e.g. `nuclei_flag` (True / False) and `nuclei_fix` (standardised text: `deleted: missing 9`, or `not fixed (no_changes): missing 9`; empty if nothing to do) |
| Unless `no_changes=True`, fixes the delineation IN PLACE | `d.save(voxels)` rewrites the file (same grid, header, type; written then renamed), `d.delete()` removes it |
| Saving the CSV and the files at the same time | The table is saved right after every file a fix changes, and at the end of each problem |
| All problem functions are idempotent | Running a problem twice gives the same result as once: `nuclei` skips the files it already deleted and finds nothing new on the others (checked: 23 flagged, then 0). New problems must keep this property, e.g. a fix must not apply again to an already fixed file |
| Problem functions can call helpers | They use `helpers.py` (`load`, `get_labels`…); `d.peers()` gives the other raters of the same scan |
| A main function runs every other function | `main()` runs every problem; problems not implemented yet are reported and skipped |
| Every function can run on a single delineation | `--delineation C_001_1_3_2` (name or index); in Python, `run_problem(name, table, [index])` or `problem(Delineation(table, index))` |

```
python ANALYSIS/fix_problems.py                              # every implemented problem, fixing
python ANALYSIS/fix_problems.py --no-changes                 # only flag
python ANALYSIS/fix_problems.py --problem nuclei             # one problem
python ANALYSIS/fix_problems.py --delineation C_001_1_3_2    # one delineation
```

`build_clean_data.py` rebuilds `DELINEATION_CLEAN` from scratch, which restores deleted files and removes
the problem columns: rerun `fix_problems.py` after it.

### Problems

| # | Problem (instructions) | Function | Status |
|---|---|---|---|
| 1 | Do not keep files with more or fewer nuclei | `nuclei` | **Done.** Flags a mask whose labels are not exactly 1–9 (missing, extra, empty). Fix: the file is **deleted**, its row stays with the reason. On the current data: **23 delineations** (e.g. `missing 9`, `extra 10`, `missing 7; extra 12 13`); 385 remain |
| 2 | Check the left-right orientation | `lr_flip` | Not implemented. Header orientation is already handled by `build_clean_data.py`. A test that mirrored masks matching the other raters better was tried and removed: the only file it flagged (16i SUBC002_ses2) looks like a wrong scan |
| 3 | Stray points | `stray_points` | **Done.** For each label, the connected pieces (26-connectivity) are found; the **2 largest** are the main structure (each nucleus is drawn in both hemispheres, so one piece per side). Any other piece farther than **5 mm** (`STRAY_MARGIN_MM`) from them is stray. Fix: the stray voxels are **set to 0**, the file is rewritten in place. Fix text: `fixed: 231 voxels removed (label 4: 3 pieces, 231 voxels)`. On the current data (after problem 1): **143 of 383 delineations**, 2,493 voxels removed in total (median 3 per file, max 822 on `C_003_2_16_2`, a probable wrong scan). Idempotent (checked: 143 flagged, then 0). ~2 min 40 s |
| 4 | Incomplete delineation | `incomplete` | Not implemented. The viewer flags abnormal volumes (< 50 % or > 200 % of the median) |
| 5 | Swapped labels | `swapped_labels` | Not implemented. Analysis so far: labels 1–6 are almost always right; mix-ups concern nuclei 7, 8, 9, and some raters used 10–13 or 35 for them (e.g. 3g: 12 → 9, 13 → 7; 5e: 35 → 9). Note: problem 1 currently deletes these files before problem 5 could relabel them |
| 6 | Points placed far from the nuclei by mistake | `far_points` | Not implemented. Close to problem 3 |
| 7 | Rater stopped halfway | `stopped_halfway` | Not implemented. Close to problem 4 |
| 8 | Missing frames | `missing_frames` | Not implemented. The viewer flags gaps between slices |
| 9 | Shifted delineation / wrong scan | `shifted_scan` | Not implemented. Known suspects: 16i SUBC002–004_ses2 (look like SUBG002–004_ses2), headers with a different origin (6j, 9b, 10j, 7c) |

The detection parameters of the old instructions (distance to the main block, piece size, number of pieces; centre vs median, mean Dice) are not used yet, except the distance (5 mm margin of `stray_points`).

---

## Staple and `staple.py`

| Instruction | Implementation |
|---|---|
| For each scan with three or more delineations | 83 of the 110 scans before `fix_problems.py`, 78 after it (problem 1 leaves 5 more scans with fewer than 3 raters) |
| Takes the clean delineations | Reads `DATA/DELINEATION_CLEAN/delineations.csv`, skipping rows whose file was deleted by `fix_problems.py` |
| Applies STAPLE → reference delineations | Multi-label STAPLE (Warfield et al. 2004), in numpy. Estimates at the same time the most probable delineation and each rater's reliability, so an unreliable rater weighs less than in a majority vote |
| Saves them in `DATA/STAPLE` | `DATA/STAPLE/<scan>_staple.nii.gz`, e.g. `C_001_1_staple.nii.gz` (labels 0–9, same grid as the masks) |
| Report with statistics | `RESULTS/staple_report.md` (overview, agreement per nucleus, scans and masks with the least agreement), plus `staple_report_raters.csv` (per mask: Dice per nucleus, STAPLE sensitivity, volume) and `staple_report_scans.csv` (per scan: convergence, reference volumes, unanimous / uncertain voxels, weakest rater) |
| A line on the problems run or not when `staple.py` ran | First line of the report, read from the `<problem>_flag` / `_fix` columns of `delineations.csv`: for each of the 9 problems, *not run*, *flagged only (no_changes)* or *fixed*, with the number flagged. E.g. `nuclei: fixed, 23 flagged; lr_flip: not run; …` |

How it is made fast and safe: voxels with exactly the same votes are grouped and computed once (identical
result, ~1 s for a 9-rater scan); scans run in parallel; each finished scan is saved immediately, and
`--resume` continues after an interruption.

Last test run (real data, in a scratch copy, after `fix_problems.py`): 78 scans; median mean Dice 1–9 of a rater
vs the reference 0.77, whole-thalamus Dice 0.88; 14 masks with a mean Dice < 0.5; 3 scans did not converge.

---

## Things to worry about

1. **Wrong scans are in the clean data.** 16i's SUBC002–004_ses2 (now raters `16_2`) very likely delineate
   SUBG002–004_ses2. They are copied into `DELINEATION_CLEAN` and used by STAPLE (16i on C_002_2: mean Dice 0.17).
   STAPLE gives them little weight, but they should be moved or excluded once confirmed.
2. **Problem 1 deletes masks that could be saved.** Of the 23 deleted delineations, many only have nuclei 7–9
   renumbered (labels 10–13, 35): a relabelling (problem 5) would keep them. Swapped labels that still use 1–9
   are not detected at all and remain in STAPLE, where they count as disagreements.
3. **3 scans did not converge in STAPLE** within 1000 iterations (C_009_1, C_017_1, C_025_2; mean Dice 0.51–0.71).
   Their reference is less reliable; see `converged` in `staple_report_scans.csv`. (A minimum of 2 raters was
   tried and dropped: with 2 raters STAPLE cannot tell which one is more reliable and never converges.)
4. **The label ↔ nucleus mapping is not confirmed.** Everything works by label number; the nucleus names
   (label 1 = LGN… 9 = CM, from `colors.md`) are an assumption, contradicted at least once (SUBC049, rater 7a).
5. **Manual corrections rely on what the team said.** `NAME_FIXES` (e.g. every 6j file is ses1) cannot be
   checked without the assignment spreadsheet, which is not on every machine.
6. **The duplicate rule relies on file dates.** "Keep the most recently modified" assumes the modification dates
   survived the Drive download; it gives the right answer on the two current cases (the newer file is complete).
   It already gives different results on different machines: on one local copy (2026-11-23) rater 15a's
   SUBG009_ses1 `.nii` / `.nii.gz` pair was not treated as a duplicate the same way, and `nuclei` then flagged
   **25** delineations instead of 23. Everyone should work from the same download, or the rule should not depend on dates.
7. **The viewer cannot draw deleted delineations.** `fix_problems.py` deletes the file and `delineations.csv` does
   not record which raw file each clean file came from, so the viewer lists them (red, with the reason) but cannot
   show what was wrong. Keeping an `original_file` column in `delineations.csv` would allow it (instructions change).
8. **Generated data must be rebuilt after a code change**, in order: `build_clean_data.py`, `fix_problems.py`,
   `staple.py`, `build_viewer.py`. Rerunning `build_clean_data.py` alone brings back the deleted files. The viewer's
   STAPLE layer is only as recent as the last `staple.py` run.
9. **Rerunning a fixing problem erases the record of what it fixed.** On a second run, `stray_points` finds nothing
   left and rewrites its columns as `False` / empty: the `fixed: … voxels removed` text of the first run is lost (and
   `staple.py` then reports `stray_points: run, 0 flagged`). `nuclei` is not affected (it skips deleted files). To
   keep the trace, run `fix_problems.py` once after `build_clean_data.py`, or keep the previous fix text when a
   rerun finds nothing (not done: it would change what `_flag` means).
10. **Stray points: pieces 2–5 mm away are kept on purpose.** A 2 mm margin was tried first: it removed real parts of
   nuclei, e.g. pieces of 50–100 voxels 3 mm below the nucleus on both sides (C_001_2 rater 7_2, G_008_1 rater 14_6),
   i.e. a nucleus cut by 1–2 empty slices. These gaps are problem 8 (missing frames). Margins and their effect:
   2 mm → 246 files / 4,688 voxels, 3 mm → 175 / 3,107, 5 mm → 152 / 2,621, 7 mm → 144 / 2,536 (before problem 1).
   Beyond 5 mm the removed pieces are 7–70 mm away and mostly 1–2 voxels. A nucleus drawn on one side only would keep
   its 2nd largest piece even if it is stray (rule "2 largest pieces", chosen over a minimum size).
11. **Old files left in `RESULTS/`**: `01_inventory.csv`, `02_easy_clean.csv` (from deleted scripts, with local changes)
   and `02_new_delineations.csv`, `02_new_subjects.csv` (from the old `02_new_clean.py`). Nothing reads them; they
   could not be deleted automatically and are left for you to remove.

## Suggested changes to `analysis_instructions.md`
- The "Problems" list of "Further problems" and the "Definition précise des problèmes" section are still in French.
- Decide what to do with known wrong scans (16i SUBC002–004_ses2).
- Problems 3 / 6 and 4 / 7 overlap (stray points vs points far from the nuclei; incomplete vs stopped halfway):
  they could be merged, or their difference made explicit.
- Problem 5 (swapped labels) should probably run before problem 1, so that relabelled masks are not deleted.

## Decision history

- 2026-11-15 — The left-right flip test (mirroring a mask that matches the other raters better mirrored) was
  removed: the only file it flagged was a probable wrong scan.
- 2026-11-15 — `subjects.csv` (one row per C|G ID) was removed: nothing used it and it can be derived from
  `delineations.csv`.
- 2026-11-15 — `build_clean_data.py` made 15× faster (~105 s → ~7 s): MRI test only on float files, duplicate
  fingerprint only for files that have a duplicate, raw files read in parallel. Output identical.
- 2026-11-15 — `fix_problems.py` created (architecture of "Further problems"): 9 problem functions, problem 1
  (`nuclei`) implemented from the former `checks.test_labels`; `checks.py` deleted. Fix for problem 1: the file
  is deleted and its row kept; `staple.py` and the viewer skip deleted files.
- 2026-11-15 — `report.csv` renamed `build_clean_data_report.csv`, so its name says which script wrote it.
- 2026-11-15 — `03_staple.py` renamed `staple.py` and updated to the new instructions: scans with 2 or more
  raters (was 3), and a report line on the `fix_problems.py` problems run or not.
- 2026-11-15 — STAPLE back to 3 raters minimum (instructions updated). Every report is named after the script that
  writes it + `_report` and saved in `RESULTS/`: `build_clean_data_report.csv` (moved from `DATA/DELINEATION_CLEAN`),
  `staple_report.md`, `staple_report_raters.csv`, `staple_report_scans.csv` (were `03_staple_*`).
- 2026-11-15 — `explore_delineations.ipynb` added (data summary charts); `matplotlib==3.11.2` added to `requirements.txt`.
- 2026-11-23 — Viewer (branch `dataviz2`) based only on the clean data: one page per scan (no subject / session
  selectors, no Clean / Excluded filter); raw files and `build_clean_data_report.csv` no longer read; each delineation
  shows its `<problem>_flag` / `_fix` columns (problems without columns = *not run*, list taken from
  `fix_problems.PROBLEMS`); files deleted by `fix_problems.py` listed in red with the reason (not drawable); STAPLE
  reference added as an extra layer when `DATA/STAPLE/<scan>_staple.nii.gz` exists. Notes are now keyed by the clean
  file path and exported as `scan, group, rater, file, problems_flagged, note, date`.
- 2026-11-23 — Viewer: manual review. For each delineation, the automatic errors (`fix_problems.py` flags + viewer checks,
  grouped per type / label / side) can be confirmed or rejected with a comment, errors can be added by hand (type from
  the problems of `analysis_instructions.md`, label, side, cursor position, comment) and the delineation ticked
  *reviewed*. Export as `review_viewer_<date>.xlsx` (sheets `Delineations` and `Errors`), replacing the notes CSV.
  Stored in the browser only. The manual flags are not read back by the pipeline yet: they are meant to decide which
  problem functions to implement and to check them.
- 2026-11-25 — Problem 3 `stray_points` implemented (instruction: a voxel not adjacent, with some margin, to the main
  structure is deleted). Main structure = the 2 largest connected pieces of each label (the largest alone would
  delete a hemisphere: 2,868 label masks have exactly 2 pieces, left and right). Margin 5 mm instead of 2 mm (see
  "Things to worry about" 10). Work done in the box around the delineation (~0.4 s per file instead of ~2 s).
- 2026-11-25 — `run_problem` fix: with pandas 3, a `_flag` column read back from the CSV with empty cells (rows of
  deleted files) is typed `str` and refused booleans, so a second run of any problem after `nuclei` crashed. The
  columns are now converted to `object` before writing.
