"""
02_new_clean.py — Reorganises DATA/DELINEATION_DATA by scan into DATA/NEW_CLEAN_DELINEATION.

Spec (docs/consigne_analyse.md, "02_new_clean.py - new version", plus instructions of 2026-11-15):
  - takes all the delineations in DELINEATION_DATA;
  - one folder per scan (C|G + ID + session), files renamed '{G|C}_<ID>_{1|2}_<rater>.nii.gz':
        NEW_CLEAN_DELINEATION/C_001_1/C_001_1_3_2.nii.gz
  - raters with no delineation (empty folder) are removed; the rater ID is '<group>_<number>': the group
    number is kept and the raters of each group are numbered 1, 2, 3... in their original letter order.
    If Group 3 has 3a (empty), 3b and 3d, they become 3_1 and 3_2;
  - subject and session read from the file name; known mistakes of some raters are corrected with
    NAME_FIXES (9b ses9, 6j: every file is ses1, 5f, 5a and 8b without C/G); a file still unreadable is not copied;
  - file type: checked from the content, not the extension. NIfTI files are written as real .nii.gz
    (.nii, .nii.gz.gz, .zip, uncompressed '.nii.gz' converted, NIfTI content unchanged);
    files that are not NIfTI are not copied. Both are reported;
  - MRIs (non-integer values instead of labels) are not copied;
  - orientation: a header that is not RAS is reoriented to RAS (same voxels, axes flipped / swapped);
    a file whose grid is still not 192x224x224 at 1 mm after that is not copied;
  - left-right flip: in a scan with 3 or more raters, each mask is compared with the majority of the
    other raters, as it is and mirrored left-right; if the mirrored one matches clearly better
    (Dice gain > 0.10, same test as checks.find_lr_flips), the mask is written back mirrored;
  - duplicates (same rater, same scan): exact copies (same voxels) -> one is copied;
    different content -> the most recently modified file is kept (earlier ones were unfinished saves);
  - dataframes, saved next to the delineations: subjects (one G|C_ID per row) and
    delineations (index, filepath, scantype, delineationID, session, raterID).

Outputs, all in DATA/NEW_CLEAN_DELINEATION/ (emptied and recreated on every run):
  <scan>/<scan>_<rater>.nii.gz   the delineations
  subjects.csv, delineations.csv the dataframes
  report.csv                     every raw file that was not copied as it was: wrong type, MRI,
                                 reoriented, duplicate, unreadable subject / session...
Never modifies DATA/DELINEATION_DATA.
Usage: python ANALYSIS/02_new_clean.py
"""

import gzip
import hashlib
import re
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd

from checks import FLIP_MARGIN, dice, downsample, fix_orientation, get_labels, scan_key, split_name

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "DATA" / "DELINEATION_DATA"
OUT = ROOT / "DATA" / "DELINEATION_CLEAN"
ACTIONS = {"wrong type": "converted to .nii.gz", "header": "reoriented", "name corrected": "placed with the corrected name"}


def rater_order(folder):
    """'Rater 16i' -> (16, 'i'): Group 1 -> 16, then a -> k."""
    m = re.fullmatch(r"Rater (\d+)([a-z]+)", folder.name.strip())
    return (int(m.group(1)), m.group(2)) if m else (999, folder.name)


# ================================================================ names
# Name corrections given by the team (2026-11-15), keyed by the original rater folder.
# A correction only fills a part of the name that is missing or impossible (no C/G, session not 1-2),
# unless "always" is set: then it replaces that part in every file of the rater.
NAME_FIXES = {
    "9b": {"session": "1"},                     # SUBC009_ses9: meant ses1
    "6j": {"session": "1", "always": True},     # numbered their files ses1 ... ses7: all are ses1
    "5f": {"scantype": "C"},                    # SUBJEC35 ... SUBJEC37: no C/G, they are C
    "5a": {"scantype": "C", "session": "1"},    # 'Sub 32- Final': no type and no session
    "8b": {"scantype": "C"},                    # SUB008_ses2: no C/G, it is C
}


def read_scan(filename, original_rater):
    """(scantype, ID, session) read from the file name, with NAME_FIXES applied.
    Returns (parts or None if still unreadable, list of corrections made, what was read)."""
    read = scan_key(filename) or ""
    m = re.fullmatch(r"SUB([CG?])(\d{3})_ses(\d|\?)", read)
    if m:
        scantype, sid, session = m.groups()
    else:  # e.g. 'Sub 32- Final': only a number after 'sub'
        n = re.search(r"sub\D*(\d+)", filename, re.I)
        scantype, sid, session = "?", (f"{int(n.group(1)):03d}" if n else None), "?"
    fix, corrections = NAME_FIXES.get(original_rater, {}), []
    if "scantype" in fix and scantype != fix["scantype"] and (scantype not in ("C", "G") or fix.get("always")):
        corrections.append(f"type {scantype} -> {fix['scantype']}")
        scantype = fix["scantype"]
    if "session" in fix and session != fix["session"] and (session not in ("1", "2") or fix.get("always")):
        corrections.append(f"session {session} -> {fix['session']}")
        session = fix["session"]
    if sid and scantype in ("C", "G") and session in ("1", "2"):
        return (scantype, sid, session), corrections, read
    return None, corrections, read or "nothing"


def rater_key(rater_id):
    """'16_2' -> (16, 2), so that rater 2_1 comes before 10_1."""
    group, number = rater_id.split("_")
    return (int(group), int(number))


# ================================================================ file type
def is_nifti(b):
    return b[344:348] in (b"n+1\x00", b"ni1\x00") or b[4:8] in (b"n+2\x00", b"ni2\x00")


def unpack(path):
    """Reads the file whatever its extension. Returns (NIfTI bytes or None, container, description).
    container: list of layers around the NIfTI, e.g. ['gzip'] for a real .nii.gz, [] for a .nii."""
    raw, layers = path.read_bytes(), []
    if raw[:2] == b"PK":
        layers.append("zip")
        try:
            with zipfile.ZipFile(path) as z:
                members = [n for n in z.namelist() if ".nii" in n and not n.startswith("__MACOSX")]
                if len(members) != 1:
                    kind = "Word document" if "word/document.xml" in z.namelist() else "zip archive"
                    return None, layers, f"{kind}, no NIfTI inside"
                raw = z.read(members[0])
        except zipfile.BadZipFile:
            return None, layers, "damaged zip archive"
    while raw[:2] == b"\x1f\x8b":
        layers.append("gzip")
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError):
            return None, layers, "damaged gzip file"
    if is_nifti(raw):
        return raw, layers, "NIfTI" + "".join(f" in {x}" for x in reversed(layers))
    if raw[4:8] == b"Bud1":
        return None, layers, "macOS .DS_Store (folder settings)"
    return None, layers, "unknown file type (not NIfTI)"


def read_image(nifti):
    cls = nib.Nifti2Image if nifti[4:8] in (b"n+2\x00", b"ni2\x00") else nib.Nifti1Image
    return cls.from_bytes(nifti)


def voxel_hash(data):
    """Fingerprint of the voxel values, independent of the storage type (uint8, float32...)."""
    return hashlib.md5(np.ascontiguousarray(np.round(data).astype(np.int32)).tobytes()
                       + str(data.shape).encode()).hexdigest()


# ================================================================ main
def main():
    report = []  # one row per raw file not copied as it was

    def note(path, issue, action):
        report.append({"original_file": path.relative_to(RAW).as_posix(), "issue": issue, "action": action})

    # raters: non-empty folders; within each group numbered 1, 2, 3... -> ID '<group>_<number>'
    folders = [d for g in RAW.iterdir() if g.is_dir() for d in g.iterdir() if d.is_dir()]
    raters = sorted((d for d in folders if any(p.is_file() for p in d.rglob("*"))), key=rater_order)
    new_id, letters_used = {}, defaultdict(int)
    for folder in raters:
        group = rater_order(folder)[0]
        letters_used[group] += 1
        new_id[folder] = f"{group}_{letters_used[group]}"

    # pass 1: read every file, decide what to copy
    candidates = defaultdict(list)  # (scantype, ID, session, rater) -> readable masks
    for folder in raters:
        rater, original_rater = new_id[folder], folder.name.strip().replace("Rater ", "")
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            nifti, layers, kind = unpack(path)
            if nifti is None:
                note(path, f"wrong file type: {kind}", "not copied")
                continue
            parts, corrections, read = read_scan(path.name, original_rater)
            if parts is None:
                note(path, f"subject or session unreadable in the name (read: {read})", "not copied")
                continue
            img = read_image(nifti)
            data = np.asarray(img.dataobj)
            if get_labels(data) is None:
                note(path, "MRI instead of a mask (non-integer values)", "not copied")
                continue
            fixes = [f"name corrected ({c}, NAME_FIXES)" for c in corrections]
            if split_name(path.name)[1] != ".nii.gz" or layers != ["gzip"]:
                fixes.append(f"wrong type for its name: '{split_name(path.name)[1]}' is a {kind}")
            axes = "".join(nib.aff2axcodes(img.affine))
            reoriented = None
            if axes != "RAS":
                reoriented = fix_orientation(img)
                if reoriented is None:
                    note(path, f"header {axes}, grid {'x'.join(map(str, img.shape))} still wrong once reoriented",
                         "not copied")
                    continue
                fixes.append(f"header {axes} reoriented to RAS")
                data = np.asarray(reoriented.dataobj)
            elif tuple(img.shape) != (192, 224, 224) or not np.allclose(img.header.get_zooms()[:3], 1, atol=0.01):
                note(path, f"wrong grid {'x'.join(map(str, img.shape))}", "not copied")
                continue
            small = downsample(data > 0)  # coarse thalamus mask, enough to see a left-right flip
            candidates[(*parts, rater)].append(
                {"path": path, "layers": layers, "fixes": fixes, "hash": voxel_hash(data),
                 "reoriented": reoriented is not None, "small": (np.packbits(small), small.shape)})

    # duplicates: same rater, same scan
    kept = {}
    for key, files in candidates.items():
        if len({f["hash"] for f in files}) > 1:
            # different content: keep the most recently modified file (earlier ones are unfinished saves)
            best, *older = sorted(files, key=lambda f: -f["path"].stat().st_mtime)
            for o in older:
                if o["hash"] == best["hash"]:
                    note(o["path"], f"duplicate: exact copy of {best['path'].relative_to(RAW).as_posix()}", "not copied")
                else:
                    note(o["path"], f"duplicate: older version of {best['path'].relative_to(RAW).as_posix()} "
                                    f"(different content)", "not copied (the latest file is kept)")
            kept[key] = best
            for fix in best["fixes"]:
                note(best["path"], fix, next(a for k, a in ACTIONS.items() if fix.startswith(k)))
            continue
        best, *copies = sorted(files, key=lambda f: (f["layers"] != ["gzip"], str(f["path"])))
        for c in copies:
            note(c["path"], f"duplicate: exact copy of {best['path'].relative_to(RAW).as_posix()}", "not copied")
        kept[key] = best
        for fix in best["fixes"]:
            note(best["path"], fix, next(a for k, a in ACTIONS.items() if fix.startswith(k)))

    # left-right flip: each mask vs the majority of the other raters of the same scan (same test as
    # checks.find_lr_flips). If the mirrored mask matches clearly better, it is written back mirrored.
    by_scan = defaultdict(list)
    for key in kept:
        by_scan[key[:3]].append(key)
    for keys in by_scan.values():
        if len(keys) < 3:
            continue  # fewer than 2 other raters: no reliable majority to compare with
        masks = {k: np.unpackbits(kept[k]["small"][0], count=int(np.prod(kept[k]["small"][1])))
                 .reshape(kept[k]["small"][1]).astype(bool) for k in keys}
        total = np.sum(list(masks.values()), axis=0, dtype=np.int16)
        for k, m in masks.items():
            reference = (total - m) > (len(keys) - 1) / 2
            d, d_flip = dice(m, reference), dice(m[::-1], reference)
            kept[k]["flip"] = bool(d_flip > d + FLIP_MARGIN)
            if kept[k]["flip"]:
                note(kept[k]["path"], f"left-right flipped compared with the other {len(keys) - 1} raters "
                                      f"(Dice {d:.2f}, mirrored {d_flip:.2f})", "unflipped")

    # pass 2: write
    if OUT.exists():
        assert OUT.name == "NEW_CLEAN_DELINEATION" and OUT.parent.name == "DATA"
        shutil.rmtree(OUT)  # generated folder: recreated on every run
    rows = []
    for (scantype, sid, session, rater), f in sorted(kept.items(), key=lambda kv: (kv[0][:3], rater_key(kv[0][3]))):
        scan = f"{scantype}_{sid}_{session}"
        dst = OUT / scan / f"{scan}_{rater}.nii.gz"
        dst.parent.mkdir(parents=True, exist_ok=True)
        flip = f.get("flip", False)
        if f["layers"] == ["gzip"] and not f["reoriented"] and not flip:
            shutil.copy2(f["path"], dst)  # already a real .nii.gz: identical copy
        else:
            nifti = unpack(f["path"])[0]
            if f["reoriented"] or flip:
                img = read_image(nifti)
                if f["reoriented"]:
                    img = fix_orientation(img)
                if flip:  # mirror the voxels along the left-right axis (axis 0 in RAS), header unchanged
                    img = img.__class__(np.asarray(img.dataobj)[::-1].copy(), img.affine, img.header)
                nifti = img.to_bytes()
            dst.write_bytes(gzip.compress(nifti, compresslevel=6))
        rows.append({"filepath": dst.relative_to(ROOT).as_posix(), "scantype": scantype,
                     "delineationID": sid, "session": int(session), "raterID": rater})

    # dataframes, next to the delineations
    delineations = pd.DataFrame(rows)
    delineations.index.name = "index"
    subjects = (delineations[["scantype", "delineationID"]].drop_duplicates()
                .assign(subject=lambda d: d.scantype + "_" + d.delineationID)
                [["subject", "scantype", "delineationID"]].reset_index(drop=True))
    report_df = pd.DataFrame(report, columns=["original_file", "issue", "action"]).sort_values("original_file")
    delineations.to_csv(OUT / "delineations.csv", encoding="utf-8-sig")
    subjects.to_csv(OUT / "subjects.csv", index=False, encoding="utf-8-sig")
    report_df.to_csv(OUT / "report.csv", index=False, encoding="utf-8-sig")

    # summary
    n_raw = sum(1 for d in raters for p in d.rglob("*") if p.is_file())
    print(f"{len(delineations)} delineations written to {OUT.relative_to(ROOT)}/ from {n_raw} raw files: "
          f"{delineations.filepath.str.split('/').str[2].nunique()} scans, {len(subjects)} subjects")
    print(f"{len(raters)} raters kept, numbered <group>_<n> within each group "
          f"({len(folders) - len(raters)} empty folders removed)")
    print("Report (report.csv):")
    summary = report_df.assign(issue=report_df.issue.str.replace(r"[:(].*", "", regex=True).str.strip())
    for (issue, action), k in summary.groupby(["issue", "action"]).size().sort_values(ascending=False).items():
        print(f"   {k:3d}  {issue} -> {action}")
    for _, r in report_df[report_df.action.str.startswith("not copied")].iterrows():
        print(f"      not copied: {r.original_file}  ({r.issue})")


if __name__ == "__main__":
    main()
