# Delineation viewer

**Local** web page with two uses:
1. **Compare the raters** of one subject: overlay, hide, isolate, filter by label, see the agreement (Dice).
2. **Detect errors** not yet covered by the analysis (stray points, incomplete delineation,
   missing slices, abnormal volumes), **note** them, then export the notes to report them in the instructions
   and fix them afterwards in the cleaning (`build_clean_data.py`) or as a problem function (`fix_problems.py`).

Everything runs in the browser, without a server. No data is sent online.

**Quick use**: choose a subject → click a delineation on the left → read its alerts in
the *Checks* panel → **go** button to see the problem on the slices → write a note →
**Export notes** at the top right.

---

## 1. Files

| File | Role |
|---|---|
| `ANALYSIS/viewer/build_viewer.py` | Reads the masks (with `ANALYSIS/helpers.py`, like the analysis), prepares the page's data |
| `ANALYSIS/viewer/index.html` | Code of the page (template, copied on each build) |
| `RESULTS/viewer/index.html` | **The page to open** (generated) |
| `ANALYSIS/viewer/build_tables.py` | Copies every `RESULTS/**/*.csv` and `DATA/DELINEATION_CLEAN/*.csv` into `RESULTS/viewer/data/tables.js` (a few seconds; also run by `build_viewer.py`) |
| `ANALYSIS/viewer/tables.html` → `RESULTS/viewer/tables.html` | CSV reader ("CSV tables" link in the viewer): one tab per CSV of the project; sort, search, filter per column. "+ Other CSV…" for any other file (e.g. `notes_viewer.csv`) |
| `RESULTS/viewer/data/*.js` | Generated data, one file per subject (~27 MB, ignored by git) |
| `requirements.txt` | Required Python packages |

Inputs read (never modified), all produced by `ANALYSIS/build_clean_data.py`:
- `DATA/DELINEATION_CLEAN/` and its `delineations.csv`: the cleaned delineations, shown as *clean* or *fixed*
  (rows whose file was deleted by `fix_problems.py` are not shown);
- `RESULTS/build_clean_data_report.csv`: what the cleaning did to each raw file (status and reason);
- `DATA/DELINEATION_DATA/`: only the raw files the cleaning did not copy, shown as *excluded*.

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
.venv/bin/python ANALYSIS/build_clean_data.py      # DATA/DELINEATION_CLEAN + delineations.csv, RESULTS/build_clean_data_report.csv
.venv/bin/python ANALYSIS/viewer/build_viewer.py   # page data + checks (~1 min 30 Mac, ~5 min Windows)
open RESULTS/viewer/index.html                 # or double-click in the Finder
```

On Windows (PowerShell): `.venv\Scripts\python ANALYSIS\viewer\build_viewer.py` then `start RESULTS\viewer\index.html`.

- To update a few subjects only: `build_viewer.py C_001 G_009`. The other subjects are kept.
- After a new build, a simple reload of the page is enough: the data files carry a version
  number, so the browser does not reuse the old cached version.

---

## 4. Use

**Header**
- **Data**: chooses which delineations are visible.
  - *Clean*: the content of `DATA/DELINEATION_CLEAN` (default).
  - *Uncorrected*: the delineations copied unchanged from the raw data.
  - *Excluded*: the raw files `build_clean_data.py` did not copy, with the reason.
  - *All*: clean and excluded together.
- **Subject**: only shows the subjects with at least one delineation under the filter, with their number.
- **Session**: ses1 / ses2 / all. By default, the session with the most delineations.
- **Export notes**: downloads `notes_viewer.csv` (every note, every subject).
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
- **Checkbox**: show / hide the delineation. **solo** shows only that one.
- **Click on the row**: selects it (blue frame) and shows its checks in the *Checks* panel.
- Each row sums up its alerts: red ● = viewer checks (green ● = no alert). 📝 = a note exists.
- Keyboard: keys **1–9** to toggle the n-th delineation, **Space** to swap the visible ones
  (useful to alternate between two raters).
- **Labels**: show only some labels (shown by number **L1–L9**; the assumed nucleus name
  appears on hover). The filter also applies to the Dice.

***Checks* panel** (selected delineation)
- Table per label and per side: voxels, median of the other raters, isolated / detached fragments, gaps.
  Red cells are worth a look.
- List of the **fragments** and **gaps**: the **go** button puts the cursor on it and circles it in yellow.
- **Note**: free text, saved automatically (see § 5c).

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

### a. Badge and text: `RESULTS/build_clean_data_report.csv`

| Badge | Meaning | Text shown |
|---|---|---|
| ✓ clean | copied unchanged from the raw data | — |
| ✓ fixed | copied with a change | what was done (converted to .nii.gz, reoriented, name corrected) |
| ✗ excluded | raw file not copied into `DELINEATION_CLEAN` | the reason (wrong file type, MRI, duplicate, unreadable name…) |

### b. Viewer checks (red ●): computed by `build_viewer.py`

**Exploratory** checks, to spot problems. They are not in `build_clean_data.py`:
a problem confirmed by eye should be reported in the instructions, then added to the cleaning.

Each label is **bilateral**: normally one block on the left and one block on the right. For each label:
1. The mask is split into **pieces** (connected components, 26-connectivity: two voxels touching
   even by a corner belong to the same piece).
2. Each piece is assigned to a **side** according to its position relative to the left-right centre of the delineation.
3. On each side, the biggest piece is the **main block**; the others are **fragments**:
   - **isolated**: more than 3 mm from the main block → probable stray point (counted in the alert);
   - **detached**: 3 mm or less → often a skipped slice or a brush stroke (detail only).
4. **Gaps between slices**: on each axis, an empty slice between the first and the last slice of the label
   (main block + detached fragments). Probable sign of a **forgotten slice** ("missing frame").
5. **Abnormal volume**: voxels of the label on this side < 50 % or > 200 % of the **median** of the delineations
   of the same session under the current filter (at least 3 delineations). Possible sign of a delineation
   **stopped halfway**, a forgotten label or swapped labels.
6. **Outside the frame**: the slice frame is computed for each subject over **all** its delineations
   (0.1 %–99.9 % percentiles on each axis, + 12 mm). Voxels outside the frame cannot be shown on
   the slices: they appear **in red in the overview**.

Limits:
- The side is estimated by position: a fragment crossing the midline can be counted on the wrong side.
- A label delineated on one side only gives a "missing" volume on the other side (on purpose).
- On the first data (373 clean delineations): 162 have at least one isolated fragment, 127 a gap
  and 86 voxels outside the frame. Many isolated fragments are 1 voxel: to be sorted by eye before making a rule.

### c. Notes

- One note per delineation (*Checks* panel), saved automatically **in this browser**
  (`localStorage`): it is not in the project and can be lost (private browsing, cleared cache,
  another browser or another computer).
- **Export notes** regularly: `notes_viewer.csv` (subject, session, group, rater, file, status, note, date).
- Notes stay after a new build: they are attached to the path of the raw file.

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
3. **Subject and session.**
   - Clean / fixed delineations: from `delineations.csv` (subject `C_001`, session `1`), so the name
     corrections of `build_clean_data.py` apply.
   - Excluded raw files: read from the original name, with `scan_key` of `helpers.py`
     (`SUBC20`, `SUBCO20`, `ses01`, `S2`…). A missing C/G letter gives a subject `?_###`, placed at the end of the list.
4. **What is shown.** Any readable file containing a non-empty integer mask.
   MRIs saved instead of the mask, empty masks, the `.docx` and `.DS_Store` are never shown.
5. **Rater IDs.** Clean / fixed delineations use the new IDs of `build_clean_data.py` (`3_2`);
   excluded raw files keep their folder name (`3b`), since they were never renumbered.

---

## 7. To know before interpreting

- **Do not compare ses1 and ses2 in the same view**: they are two different, non-aligned MRIs.
  The viewer says so and disables the Dice in that case.
- **Known wrong scans appear under the subject of their name**, hence the wrong one
  (e.g. 16i `SUBC002_ses2` = actually `SUBG002_ses2`). They are in *Clean*, visibly shifted compared with
  the other raters.
- **No background MRI**: only the masks are shown (MRIs not yet in `DATA/`).
- **Labels outside 1–9** (10, 11…): shown in white, without a nucleus name.
- **Files in `.nii`, `.gz.gz`, `.zip`**: decompressed **in memory** for display.
  No file of `DATA/` is modified.
- **Colours per delineation**: 8 colours; beyond 8 delineations, the colours repeat.
  Preferably compare 2 or 3 raters at a time.

---

## 8. Troubleshooting

| Symptom | Cause / solution |
|---|---|
| `ModuleNotFoundError: nibabel` or `scipy` | Script run with the wrong Python: use `.venv/bin/python`, or rerun `pip install -r requirements.txt` |
| "No data" page | `build_viewer.py` not run yet |
| "Outdated data for …" | File generated by an older version: rerun `build_viewer.py`, then Cmd+Shift+R (Ctrl+Shift+R on Windows) |
| Notes gone | Another browser, private browsing or cleared cache: the notes are in the browser, hence the CSV export |
| Empty subject + sessions warning | Old cache: Cmd+Shift+R |
| "missing: run build_clean_data.py first" when building | `DATA/DELINEATION_CLEAN/delineations.csv` or `RESULTS/build_clean_data_report.csv` missing: run `build_clean_data.py` |
| A subject is missing from the list | No delineation under the chosen filter: switch to *All* |
