"""
fix_problems.py — Further problems of the cleaned delineations (analysis_instructions.md,
"Further problems and fix_problems.py").

Works on DATA/DELINEATION_CLEAN (output of build_clean_data.py) and its delineations.csv.

One function per problem, all with the same signature:
    problem(d, no_changes=False) -> (flag, fix)
  d           one delineation (class Delineation: its row, its file, its voxels, the other raters of its scan)
  flag        True if the delineation has the problem
  fix         standardised text of what was done ('' if nothing): e.g. 'deleted: missing 9',
              or 'not fixed (no_changes): missing 9' when no_changes=True
  no_changes  True: only flag, never touch the file. False: fix the file IN PLACE.

run_problem() applies one problem to every delineation (or to some of them) and writes the two columns
'<name>_flag' and '<name>_fix' into delineations.csv. The table is saved right after every file that a fix
changes (and at the end of each problem), so the files and the table never get out of sync. Delineations whose file was deleted by an earlier fix
are skipped (their columns keep the values that explain why they were deleted).

Problems (PROBLEMS below, in the order of the instructions):
  nuclei          1. more or fewer nuclei than 1-9                  -> implemented: the file is deleted
  lr_flip         2. left-right orientation                          -> not implemented yet
  stray_points    3. stray points                                    -> implemented: stray voxels set to 0
  incomplete      4. incomplete delineation                          -> not implemented yet
  swapped_labels  5. swapped labels                                  -> not implemented yet
  far_points      6. points placed far from the nuclei by mistake    -> not implemented yet
  stopped_halfway 7. rater stopped halfway through the delineation   -> not implemented yet
  missing_frames  8. missing frames (slices)                         -> not implemented yet
  shifted_scan    9. shifted delineation / wrong scan                -> not implemented yet

Usage:
  python ANALYSIS/fix_problems.py                                 # every implemented problem, fixing
  python ANALYSIS/fix_problems.py --no-changes                    # only flag, change no file
  python ANALYSIS/fix_problems.py --problem nuclei                # a single problem
  python ANALYSIS/fix_problems.py --delineation C_001_1_3_2       # a single delineation (name or index)
Rerunning build_clean_data.py restores DELINEATION_CLEAN and removes these columns.
"""

import argparse
import gzip
import os
import sys
from functools import cached_property
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
from scipy import ndimage

from helpers import get_labels, load

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "DATA" / "DELINEATION_CLEAN"
TABLE = CLEAN / "delineations.csv"


# ================================================================ one delineation
class Delineation:
    """One row of delineations.csv and its file. Voxels are read on first use."""

    def __init__(self, table, index):
        self.table, self.index = table, index
        self.row = table.loc[index]
        self.path = ROOT / self.row["filepath"]
        self.name = self.path.name.removesuffix(".nii.gz")  # e.g. 'C_001_1_3_2'

    @property
    def exists(self):
        return self.path.exists()

    @cached_property
    def image(self):
        img = load(self.path)[1]
        if img is None:
            raise ValueError(f"unreadable delineation: {self.path}")
        return img

    @cached_property
    def data(self):
        return np.asarray(self.image.dataobj)

    def peers(self):
        """The other delineations of the same scan whose file still exists."""
        same = ((self.table.scantype == self.row["scantype"]) & (self.table.delineationID == self.row["delineationID"])
                & (self.table.session == self.row["session"]) & (self.table.index != self.index))
        return [d for d in (Delineation(self.table, i) for i in self.table.index[same]) if d.exists]

    def save(self, data):
        """Replaces the file IN PLACE with new voxels (same grid, header and data type)."""
        img = self.image.__class__(np.asarray(data).astype(self.image.get_data_dtype()),
                                   self.image.affine, self.image.header)
        tmp = self.path.with_name(self.path.name + ".part")  # written then renamed: never half-written
        tmp.write_bytes(gzip.compress(img.to_bytes(), compresslevel=6))
        os.replace(tmp, self.path)
        self.__dict__.pop("image", None)
        self.__dict__.pop("data", None)

    def delete(self):
        """Removes the file from DELINEATION_CLEAN (its row stays in delineations.csv)."""
        self.path.unlink()


# ================================================================ problems
EXPECTED_LABELS = set(range(1, 10))  # 9 thalamic nuclei, 0 = background


def nuclei(d, no_changes=False):
    """1. More or fewer nuclei than labels 1-9 (missing, extra or empty mask). Fix: the file is deleted."""
    labels = get_labels(d.data)
    missing, extra = EXPECTED_LABELS - labels, labels - EXPECTED_LABELS
    if not labels:
        detail = "empty mask"
    else:
        detail = "; ".join(p for p in (
            ("missing " + " ".join(map(str, sorted(missing)))) if missing else "",
            ("extra " + " ".join(map(str, sorted(extra)))) if extra else "") if p)
    if not detail:
        return False, ""
    if no_changes:
        return True, f"not fixed (no_changes): {detail}"
    d.delete()
    return True, f"deleted: {detail}"


def lr_flip(d, no_changes=False):
    """2. Left-right orientation of the mask compared with the other raters (d.peers())."""
    raise NotImplementedError


KEPT_PIECES = 2       # each nucleus is drawn in both hemispheres: its 2 largest pieces are the main structure
STRAY_MARGIN_MM = 5   # a piece closer than this to the main structure is kept: part of the nucleus cut by
                      # 1-4 empty slices (missing frames, problem 8), not a stray point (2 mm removed real pieces)
CONNECTIVITY = np.ones((3, 3, 3), bool)  # 26-connectivity: voxels touching by a face, an edge or a corner


def stray_points(d, no_changes=False):
    """3. Stray points: for each label, its 2 largest connected pieces (left and right) are the main structure;
    any other piece farther than STRAY_MARGIN_MM from them is stray. Fix: the stray voxels are set to 0."""
    data = d.data
    if not data.any():
        return False, ""
    # all the work is done in the box around the delineation (+ margin): ~20x faster than the whole volume
    box = tuple(slice(max(s.start - STRAY_MARGIN_MM - 1, 0), s.stop + STRAY_MARGIN_MM + 1)
                for s in ndimage.find_objects((data != 0).astype(np.int8))[0])
    sub = data[box]
    spacing = d.image.header.get_zooms()[:3]
    stray = np.zeros(sub.shape, bool)
    details = []
    for label in sorted(get_labels(sub) or ()):
        pieces, n = ndimage.label(sub == label, CONNECTIVITY)
        if n <= KEPT_PIECES:
            continue
        sizes = np.bincount(pieces.ravel())
        sizes[0] = 0
        main_ids = np.argsort(sizes)[::-1][:KEPT_PIECES]
        dist = ndimage.distance_transform_edt(~np.isin(pieces, main_ids), sampling=spacing)
        # a piece is stray when all its voxels are farther than the margin from the main structure
        closest = ndimage.minimum(dist, pieces, index=np.arange(1, n + 1))
        stray_ids = [i + 1 for i, c in enumerate(closest) if c > STRAY_MARGIN_MM and i + 1 not in main_ids]
        if stray_ids:
            removed = np.isin(pieces, stray_ids)
            stray |= removed
            details.append(f"label {label}: {len(stray_ids)} pieces, {int(removed.sum())} voxels")
    if not details:
        return False, ""
    detail = f"{int(stray.sum())} voxels removed ({'; '.join(details)})"
    if no_changes:
        return True, f"not fixed (no_changes): {detail}"
    cleaned = data.copy()
    cleaned[box][stray] = 0
    d.save(cleaned)
    return True, f"fixed: {detail}"


def incomplete(d, no_changes=False):
    """4. Incomplete delineation."""
    raise NotImplementedError


"""Replaces the stub `swapped_labels` in fix_problems.py (needs only numpy and ndimage, already imported there).

Also change the order of PROBLEMS so that swapped_labels runs FIRST (before `nuclei`, which deletes files):
    PROBLEMS = {f.__name__: f for f in (swapped_labels, nuclei, lr_flip, stray_points, incomplete,
                                        far_points, stopped_halfway, missing_frames, shifted_scan)}
"""

MIN_RATERS = 3          # the consensus of "the others" needs at least 2 peers (3 raters in total)
DICE_RELABEL = 0.5      # a single label is relabelled when its Dice with the consensus nucleus is above this
FLAG_DICE = 0.2         # below this the delineation barely overlaps the consensus: not a label swap, not flagged
CYCLE_MEAN_DICE = 0.5   # labels that trade places (7<->9, 7->8->9->7...) are judged TOGETHER: relabelled when
CYCLE_MIN_DICE = 0.3    # their mean Dice is >= 0.5 and none is below 0.3


def _dice(overlap, size_a, size_b):
    return 2.0 * overlap / (size_a + size_b) if size_a + size_b else 0.0


def _consensus(peer_arrays, shape):
    """Majority vote of the peers over the nuclei 1-9: a voxel gets nucleus c when MORE than half of the
    peers say c (so with 2 peers both must agree). Labels outside 1-9 vote for nothing."""
    n = len(peer_arrays)
    votes = np.zeros((len(EXPECTED_LABELS) + 1,) + shape, np.uint8)
    for arr in peer_arrays:
        for c in EXPECTED_LABELS:
            votes[c] += (arr == c)
    win = votes[1:] * 2 > n
    return np.where(win.any(axis=0), win.argmax(axis=0) + 1, 0)


def _cycles(moved):
    """Groups of labels that trade places: following label -> its best nucleus comes back to the start."""
    cycles, seen = [], set()
    for start in moved:
        path, cur = [], start
        while cur in moved and cur not in path and cur not in seen:
            path.append(cur)
            cur = moved[cur][0]
        if cur in path:
            cycles.append(path[path.index(cur):])
        seen.update(path)
    return cycles


def swapped_labels(d, no_changes=False):
    """5. Swapped labels: each label of the delineation (also 10-13, 35...) is matched to the nucleus of the
    consensus of the OTHER raters of the same scan (majority vote, without the delineation itself) that it
    overlaps most. A label whose best match is not itself is relabelled when its Dice with that nucleus is
    > 0.5 (and better than the identity's), or when it belongs to a group of labels that trade places and the
    group as a whole is good (mean Dice >= 0.5, none below 0.3). Relabelling is simultaneous (real swaps work).
    Otherwise it is only flagged; matches with a Dice < 0.2 are ignored (not a label problem: shifted scan...).
    Scans with fewer than 3 raters are only flagged (check in the viewer).
    Must run BEFORE `nuclei`, which would delete the delineation for its labels outside 1-9."""
    data = d.data
    if not data.any():
        return False, ""
    peers = [p for p in d.peers() if p.data.shape == data.shape]
    if len(peers) + 1 < MIN_RATERS:
        n = len(peers) + 1
        return True, f"not fixed (only {n} rater{'s' if n != 1 else ''}, < {MIN_RATERS}): check manually in the viewer"

    # work in the box around everything that is labelled (delineation + peers)
    union = data != 0
    for p in peers:
        union |= p.data != 0
    box = ndimage.find_objects(union.astype(np.int8))[0]
    sub = data[box]
    consensus = _consensus([p.data[box] for p in peers], sub.shape)
    if not consensus.any():
        return True, "not fixed (empty consensus of the other raters): check manually in the viewer"

    cons_size = np.bincount(consensus.ravel(), minlength=len(EXPECTED_LABELS) + 1)
    labels = [int(l) for l in np.unique(sub[sub != 0])]
    best = {}  # label -> (best nucleus, its Dice, Dice of the identity)
    for label in labels:
        mask = sub == label
        overlap = np.bincount(consensus[mask], minlength=len(EXPECTED_LABELS) + 1)
        overlap[0] = 0  # background of the consensus is not a nucleus
        if not overlap.any():
            continue  # touches no consensus nucleus: nothing to match (extra labels are problem `nuclei`)
        c = int(overlap.argmax())
        identity = _dice(overlap[label], mask.sum(), cons_size[label]) if label in EXPECTED_LABELS else 0.0
        best[label] = (c, _dice(overlap[c], mask.sum(), cons_size[c]), identity)

    # best match is not the identity, and the overlap is big enough to be about labels (not about position)
    moved = {l: v for l, v in best.items() if v[0] != l and v[1] >= FLAG_DICE}
    if not moved:
        return False, ""

    relabel = {l: v[0] for l, v in moved.items() if v[1] > DICE_RELABEL and v[1] > v[2]}
    for cycle in _cycles(moved):
        dices = [moved[l][1] for l in cycle]
        if len(cycle) > 1 and np.mean(dices) >= CYCLE_MEAN_DICE and min(dices) >= CYCLE_MIN_DICE:
            relabel.update({l: moved[l][0] for l in cycle})

    final = [relabel.get(l, l) for l in labels]
    text = lambda items: ", ".join(f"{l}->{v[0]} (Dice {v[1]:.2f})" for l, v in items)
    if relabel and len(set(final)) < len(final):  # two labels would end up with the same nucleus
        return True, f"not fixed (relabelling would merge labels): {text(moved.items())}"
    if not relabel:
        return True, f"not fixed (Dice too low to relabel): {text(moved.items())}"

    detail = text((l, moved[l]) for l in relabel)
    left = {l: v for l, v in moved.items() if l not in relabel}
    if left:
        detail += f"; flagged only: {text(left.items())}"
    if no_changes:
        return True, f"not fixed (no_changes): {detail}"
    fixed = data.copy()
    for label, c in relabel.items():
        fixed[data == label] = c  # compared with the ORIGINAL voxels: simultaneous, no label is relabelled twice
    d.save(fixed)
    return True, f"fixed: relabelled {detail}"


def far_points(d, no_changes=False):
    """6. Points placed far from the nuclei by mistake."""
    raise NotImplementedError


def stopped_halfway(d, no_changes=False):
    """7. The rater stopped halfway through the delineation."""
    raise NotImplementedError


def missing_frames(d, no_changes=False):
    """8. Missing frames (slices)."""
    raise NotImplementedError


def shifted_scan(d, no_changes=False):
    """9. Shifted delineation / wrong scan (compare with d.peers())."""
    raise NotImplementedError


PROBLEMS = {f.__name__: f for f in (nuclei, lr_flip, stray_points, incomplete, swapped_labels,
                                    far_points, stopped_halfway, missing_frames, shifted_scan)}


# ================================================================ table and runner
def read_table():
    return pd.read_csv(TABLE, index_col="index", dtype={"delineationID": str, "raterID": str},
                       keep_default_na=False)


def save_table(table):
    tmp = TABLE.with_name(TABLE.name + ".part")
    table.to_csv(tmp, encoding="utf-8-sig")
    os.replace(tmp, TABLE)


def run_problem(name, table, indices=None, no_changes=False):
    """Applies problem `name` to the delineations `indices` (default: all) and fills
    '<name>_flag' / '<name>_fix'. Returns (nb flagged, nb checked), or None if not implemented yet."""
    func, flag_col, fix_col = PROBLEMS[name], f"{name}_flag", f"{name}_fix"
    flagged = checked = 0
    for index in (table.index if indices is None else indices):
        d = Delineation(table, index)
        if not d.exists:
            continue  # deleted by an earlier fix: keep the columns that explain why
        try:
            flag, fix = func(d, no_changes=no_changes)
        except NotImplementedError:
            return None
        if flag_col not in table:
            table[flag_col] = pd.Series("", index=table.index, dtype=object)
            table[fix_col] = pd.Series("", index=table.index, dtype=object)
        elif table[flag_col].dtype != object:
            # read back from the CSV, a column with empty cells is typed 'str' (pandas 3) and refuses booleans
            table[flag_col] = table[flag_col].astype(object)
            table[fix_col] = table[fix_col].astype(object)
        table.loc[index, flag_col], table.loc[index, fix_col] = bool(flag), fix
        if flag and not no_changes:
            save_table(table)  # the file has just changed: save the table now, so both stay in sync
        flagged += bool(flag)
        checked += 1
    if checked:
        save_table(table)
    return flagged, checked


def find(table, delineation):
    """Index of a delineation given by its index or its name ('C_001_1_3_2')."""
    if delineation.isdigit() and int(delineation) in table.index:
        return int(delineation)
    match = table.index[table.filepath.str.endswith(f"/{delineation}.nii.gz")]
    if not len(match):
        sys.exit(f"Unknown delineation: {delineation}")
    return match[0]


def main(problems=None, delineation=None, no_changes=False):
    """Runs every problem (or `problems`) on every delineation (or only `delineation`)."""
    if not TABLE.exists():
        sys.exit(f"Missing {TABLE.relative_to(ROOT)}: run build_clean_data.py first")
    table = read_table()
    indices = None if delineation is None else [find(table, delineation)]
    print(f"{'Flagging only (no_changes)' if no_changes else 'Flagging and fixing'} "
          f"{'every delineation' if indices is None else table.loc[indices[0], 'filepath']}")
    for name in problems or PROBLEMS:
        result = run_problem(name, table, indices, no_changes)
        if result is None:
            print(f"   {name:16s} not implemented yet")
        else:
            print(f"   {name:16s} {result[0]:3d} flagged / {result[1]} checked")
    print(f"Table: {TABLE.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flag and fix the further problems of DELINEATION_CLEAN.")
    parser.add_argument("--no-changes", action="store_true", help="only flag, do not modify any file")
    parser.add_argument("--problem", choices=list(PROBLEMS), action="append", help="run only this problem (repeatable)")
    parser.add_argument("--delineation", help="run only on this delineation (index or name, e.g. C_001_1_3_2)")
    args = parser.parse_args()
    main(args.problem, args.delineation, args.no_changes)
