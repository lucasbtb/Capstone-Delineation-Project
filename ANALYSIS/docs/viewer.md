# Delineation viewer

**Local** web page showing **only the clean data**, i.e. the output of the analysis
(`build_clean_data.py` → `fix_problems.py` → `staple.py`), one scan at a time. Two uses:
1. **Compare the raters** of one scan, and each rater with the **STAPLE reference**: overlay, hide, isolate,
   filter by label, see the agreement (Dice).
2. **Detect errors** not yet covered by the analysis (stray points, incomplete delineation,
   missing slices, abnormal volumes), **review** them (confirm or reject each automatic error, add your own errors,
   comment), then export the review as an Excel file to report them in the instructions
   and fix them afterwards in the cleaning (`build_clean_data.py`) or as a problem function (`fix_problems.py`).

Everything runs in the browser, without a server. No data is sent online.

**Quick use**: choose a scan → click a delineation on the left → read its problems and alerts in
the *Review* panel → **go** to see each error on the slices → **confirm** / **reject** it, **+ Add error** for
what was missed, comment → tick **Reviewed** → **Export review (.xlsx)** at the top right.

---

## 1. Files

| File | Role |
|---|---|
| `ANALYSIS/viewer/build_viewer.py` | Reads the masks (with `ANALYSIS/helpers.py`, like the analysis), prepares the page's data |
| `ANALYSIS/viewer/index.html` | Code of the page (template, copied on each build) |
| `RESULTS/viewer/index.html` | **The page to open** (generated) |
| `ANALYSIS/viewer/build_tables.py` | Copies every `RESULTS/**/*.csv` and `DATA/DELINEATION_CLEAN/*.csv` into `RESULTS/viewer/data/tables.js` (a few seconds; also run by `build_viewer.py`) |
| `ANALYSIS/viewer/tables.html` → `RESULTS/viewer/tables.html` | CSV reader ("CSV tables" link in the viewer): one tab per CSV of the project; sort, search, filter per column. "+ Other CSV…" for any other file (e.g. an old `notes_viewer.csv`) |
| `RESULTS/viewer/data/*.js` | Generated data, one file per scan (e.g. `C_001_1.js`; ignored by git) |
| `requirements.txt` | Required Python packages |

Inputs read (never modified):
- `DATA/DELINEATION_CLEAN/` and its `delineations.csv` (`build_clean_data.py`, then `fix_problems.py`):
  every delineation of each scan, with its `<problem>_flag` / `<problem>_fix` columns.
  Rows whose file was deleted by `fix_problems.py` are **listed, red-flagged with the reason**, but cannot be drawn;
- `DATA/STAPLE/<scan>_staple.nii.gz` (`staple.py`, optional): the reference of the scan, shown as an extra layer.

The raw data (`DATA/DELINEATION_DATA/`) and `RESULTS/build_clean_data_report.csv` are **not** read any more:
what the cleaning did is in the CSV reader (*CSV tables* link).

How the analysis itself works: `ANALYSIS/docs/analysis_output.md`.

---

## 2. Installation (once)

```bash
cd Capstone-Delineation-Project
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On Windows, replace `.venv/bin/` with `.venv\Scripts\` in every command.
On Mac, do not use `/opt/homebrew/bin/python3` directly: nibabel is not installed there.
In VS Code, choose `.venv` as interpreter (Cmd+Shift+P → *Python: Select Interpreter*).

---

## 3. Running

Full order, to redo when the data or the cleaning change:

```bash
.venv/bin/python ANALYSIS/build_clean_data.py      # DATA/DELINEATION_CLEAN + delineations.csv
.venv/bin/python ANALYSIS/fix_problems.py          # <problem>_flag / _fix columns, fixes (e.g. deletes wrong-nuclei files)
.venv/bin/python ANALYSIS/staple.py                # optional: DATA/STAPLE references (STAPLE layer)
.venv/bin/python ANALYSIS/viewer/build_viewer.py   # page data + checks (~1 min 30 Mac, ~5 min Windows)
open RESULTS/viewer/index.html                 # or double-click in the Finder
```

On Windows (PowerShell): `.venv\Scripts\python ANALYSIS\viewer\build_viewer.py` then `start RESULTS\viewer\index.html`.

- To update a few scans only: `build_viewer.py C_001_1 G_009` (`G_009` = both sessions). The other scans are kept.
- A full build removes the data files of scans no longer in `delineations.csv`.
- After a new build, a simple reload of the page is enough: the data files carry a version
  number, so the browser does not reuse the old cached version.

---

## 4. Use

**Header**
- **Scan**: one entry per folder of `DATA/DELINEATION_CLEAN` (C|G ID + session, e.g. `C_001_1`), with its number of
  drawable delineations, of deleted ones, and whether a STAPLE reference exists. There is no session selector:
  ses1 and ses2 are different MRIs and are never overlaid.
- **Reviewer**: your name, written in the export next to every delineation you tick as reviewed.
- **Export review (.xlsx)**: downloads `review_viewer_<date>.xlsx` (every scan, see § 5c). The button shows how many
  delineations are ticked *reviewed*.
- **Settings** (menu):
  - *Display*: fill, outlines, or both;
  - *Colour*: *by delineation* (one colour per rater, the most readable to compare)
    or *by label* (colours of `colors.md`);
  - *Opacity*, *Zoom*, *Crosshair*.

**Slices**
Three views: axial, coronal, sagittal.
- Click or drag: move the crosshair.
- Wheel or slider under the view: change slice.
- The coordinates shown are those of the original volume (voxels).

**Left panel**
- **STAPLE reference** (first row, white, when `staple.py` was run): drawn like a rater, so the Dice
  compares each rater with the reference. Excluded from the volume medians.
- **Deleted** rows (name struck through, red ✗ *deleted* badge): files deleted by `fix_problems.py`, with the reason
  (e.g. `nuclei: deleted: missing 9`). No checkbox: the file no longer exists. Clicking shows its problems; it can be reviewed like the others.
- **Checkbox**: show / hide the delineation. **solo** shows only that one.
- **Click on the row**: selects it (blue frame) and shows its checks in the *Checks* panel.
- Each row sums up: red ⚑ = problems flagged by `fix_problems.py` with their fix (green ⚑ = none flagged; the number
  of problems run is shown, the names of those not run on hover); red ● = viewer checks (green ● = no alert);
  ✓ *reviewed* badge, `+n added` (your errors), `n rejected` (automatic errors you rejected), 📝 = a comment exists.
- Keyboard: keys **1–9** to toggle the n-th drawable delineation, **Space** to swap the visible ones
  (useful to alternate between two raters).
- **Labels**: show only some labels (shown by number **L1–L9**; the assumed nucleus name
  appears on hover). The filter also applies to the Dice.

***Checks* panel** (selected delineation)
- **Problems (fix_problems.py)**: one line per problem: flag (*yes*, *no*, or *not run* when its columns are
  missing) and the fix text written in `delineations.csv`.
- Table per label and per side: voxels, median of the other raters, isolated / detached fragments, gaps.
  Red cells are worth a look.
- List of the **fragments** and **gaps**: the **go** button puts the cursor on it and circles it in yellow.
***Review* panel** (selected delineation, above *Checks*): see § 5c.

**Overview**: the visible delineations projected on the **whole volume**. The dashed frame
matches the slices above; voxels outside this frame are drawn in **red** (enlarged to stay visible).
A click inside the frame moves the cursor.

**Bottom panels**
- *Under the cursor*: the label of each visible delineation at the hovered voxel.
- *Agreement (Dice)*: with 2 visible delineations, the Dice per label and the mean.
  With more than 2, the matrix of mean Dice values.
  The Dice compares **the same label**: if a rater swapped two labels, the Dice of those labels drops to ~0.
  A Dice of 0 everywhere = shifted delineations (wrong scan, different header).

---

## 5. The alerts shown

Each delineation carries a **badge**, a text next to it, and the viewer's own check alerts.

### a. Problems: the `<problem>_flag` / `<problem>_fix` columns of `delineations.csv`

Written by `fix_problems.py`, one pair of columns per problem function (`analysis_instructions.md`, *Further problems*).
The viewer reads the list of problems from `fix_problems.PROBLEMS`, so a new problem function appears automatically.

| Shown | Meaning |
|---|---|
| ⚑ red, `name: fix` | the problem flagged this delineation; the fix text says what was done |
| ✗ deleted | the fix deleted the file (e.g. `nuclei`): row listed, nothing to draw |
| ⚑ green | no problem run so far flagged it |
| *not run* (Checks panel) | the problem's columns are missing: not implemented, or `fix_problems.py` not run |

### b. Viewer checks (red ●): computed by `build_viewer.py`

**Exploratory** checks, to spot problems that no `fix_problems.py` function handles yet:
a problem confirmed by eye should be reported in the instructions, then added as a problem function.

Each label is **bilateral**: normally one block on the left and one block on the right. For each label:
1. The mask is split into **pieces** (connected components, 26-connectivity: two voxels touching
   even by a corner belong to the same piece).
2. Each piece is assigned to a **side** according to its position relative to the left-right centre of the delineation.
3. On each side, the biggest piece is the **main block**; the others are **fragments**:
   - **isolated**: more than 3 mm from the main block → probable stray point (counted in the alert);
   - **detached**: 3 mm or less → often a skipped slice or a brush stroke (detail only).
4. **Gaps between slices**: on each axis, an empty slice between the first and the last slice of the label
   (main block + detached fragments). Probable sign of a **forgotten slice** ("missing frame").
5. **Abnormal volume**: voxels of the label on this side < 50 % or > 200 % of the **median** of the raters
   of the same scan (at least 3; STAPLE reference and deleted files excluded). Possible sign of a delineation
   **stopped halfway**, a forgotten label or swapped labels.
6. **Outside the frame**: the slice frame is computed for each scan over **all** its delineations
   (0.1 %–99.9 % percentiles on each axis, + 12 mm). Voxels outside the frame cannot be shown on
   the slices: they appear **in red in the overview**.

Limits:
- The side is estimated by position: a fragment crossing the midline can be counted on the wrong side.
- A label delineated on one side only gives a "missing" volume on the other side (on purpose).
- On the first data (373 clean delineations): 162 have at least one isolated fragment, 127 a gap
  and 86 voxels outside the frame. Many isolated fragments are 1 voxel: to be sorted by eye before making a rule.

### c. Review: manual flags, rejected errors, comments, Excel export

The *Review* panel of the selected delineation has four parts:

1. **Reviewed** checkbox: tick it once you have gone through the delineation (date and reviewer name are kept).
   The panel also shows the **final list** size: automatic errors not rejected + errors you added.
2. **Automatic errors**, one row per error type, label and side (all the fragments of label 3 on the right = one row):
   - `fix_problems.py`: every problem flagged in `delineations.csv` (e.g. `nuclei: deleted: missing 9`);
   - viewer checks: *isolated fragment*, *gap between slices*, *abnormal volume*, *voxels outside the frame* (§ 5b).

   For each: **confirm** (it is an error) or **reject** (not an error: removed from the final list; the row is struck
   through), a comment, and **go** to see it on the slices. Click the same button again to go back to *not decided*.
3. **Errors you added**: choose the type (the 9 problems of `analysis_instructions.md`, the viewer check types, or
   *other*), optionally a label, a side and **the cursor position** (move the crosshair onto the error first),
   a comment, then **+ Add error**. **go** jumps back to it; ✕ deletes it.
4. **Comment** on the whole delineation (free text). Notes of the previous viewer become this comment.

Everything is saved automatically **in this browser** (`localStorage`): it is not in the project and can be lost
(private browsing, cleared cache, another browser or another computer). **Export regularly.**
Decisions are attached to the path of the clean file and to a stable error id (`isolated_fragment:3R`…), so they
stay after a new build; an error no longer detected after a rebuild is exported as *automatic (no longer detected)*.

**Export review (.xlsx)**: every delineation with something reviewed, decided, added or commented, in two sheets
(header frozen, filters on):

| Sheet | One row per | Columns |
|---|---|---|
| `Delineations` | delineation | scan, rater, group, file, deleted by fix_problems.py, reviewed, reviewer, reviewed at, number of automatic errors / confirmed / rejected / not decided / added manually, final errors, comment, last change |
| `Errors` | error | scan, rater, group, file, origin (*automatic: fix_problems.py*, *automatic: viewer check*, *manual*), error type, label, side, position (x, y, z voxels of the original volume), detail, decision (*confirmed*, *rejected*, *not decided*, *added*), in final list (yes / no), comment, reviewed, reviewer, date |

Filter the `Reviewed` column on *yes* to keep only the delineations you finished. The file is written by the page
itself (no library, no network).

---

## 6. Assumptions made

1. **Label ↔ nucleus mapping: assumed, probably wrong.**
   We assume label 1 = LGN, 2 = MGN, 3 = Pulvinar, 4 = AV, 5 = VA, 6 = VLA/VLP, 7 = VPL, 8 = MD, 9 = CM,
   from the order of `given_documents/colors.md`. Yet in SUBC049 (rater 7a), label 3 is
   ~15 mm **in front of** label 4, while the pulvinar is posterior and the AV anterior.
   That is why the viewer shows labels by **number** (L1–L9); the assumed name only appears on hover.
2. **RAS orientation, display in voxel space.**
   Every file declares RAS and is 192×224×224 at 1 mm. The masks are overlaid
   **voxel by voxel**, without taking the header origin into account. Neurological convention:
   L on the left of the screen, R on the right; axial with the front at the top; sagittal with the front on the right.
   If a header is wrong (cf. the shifted / wrong-scan delineations in `analysis_output.md`),
   the viewer does not correct it.
3. **Scan.** From `delineations.csv` (`scantype`, `delineationID`, `session` → `C_001_1`), so the name
   corrections of `build_clean_data.py` apply.
4. **What is shown.** Every row of `delineations.csv`: drawn if its file exists, listed as *deleted* otherwise,
   plus the STAPLE reference if it exists. Raw files that `build_clean_data.py` did not copy are never shown.
5. **Rater IDs.** The IDs of `build_clean_data.py` (`3_2` = group 3, rater 2 after renumbering).

---

## 7. To know before interpreting

- **One scan at a time**: ses1 and ses2 are two different, non-aligned MRIs, so they are never overlaid.
- **Known wrong scans appear under the scan of their name**, hence the wrong one
  (e.g. 16i `SUBC002_ses2` = rater `16_2` of `C_002_2`, actually `SUBG002_ses2`). Visibly shifted compared with
  the other raters; Dice ≈ 0.1 with the STAPLE reference.
- **Deleted delineations cannot be drawn**: `fix_problems.py` removed their file and `delineations.csv` does not keep
  the path of the raw file it came from.
- **The STAPLE reference depends on the raters drawn**: it was computed by `staple.py` from the files that existed
  when it ran. Rerun `staple.py` (then `build_viewer.py`) after `fix_problems.py`.
- **No background MRI**: only the masks are shown (MRIs not yet in `DATA/`).
- **Labels outside 1–9** (10, 11…): shown in white, without a nucleus name.
- **Colours per delineation**: 8 colours; beyond 8 delineations, the colours repeat.
  Preferably compare 2 or 3 raters at a time.

---

## 8. Troubleshooting

| Symptom | Cause / solution |
|---|---|
| `ModuleNotFoundError: nibabel` or `scipy` | Script run with the wrong Python: use `.venv/bin/python`, or rerun `pip install -r requirements.txt` |
| "No data" page | `build_viewer.py` not run yet |
| "Outdated data for …" or "No data" after updating the code | File generated by an older version: rerun `build_viewer.py`, then Cmd+Shift+R (Ctrl+Shift+R on Windows) |
| Review gone | Another browser, private browsing or cleared cache: the review is in the browser, hence the Excel export |
| "missing: run build_clean_data.py" when building | `DATA/DELINEATION_CLEAN/delineations.csv` missing: run `build_clean_data.py`, then `fix_problems.py` |
| Every problem "not run" | `fix_problems.py` not run since the last `build_clean_data.py` (which removes the problem columns) |
| No STAPLE row | `staple.py` not run, or the scan has fewer than 3 raters |
| "Nothing to draw" | Every delineation of that scan was deleted by `fix_problems.py` (e.g. `G_001_2`) |
