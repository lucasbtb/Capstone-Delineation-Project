"""
helpers.py — General helpers shared by the analysis scripts (reading files, parsing names, comparing masks).

No problem checks here: those live in build_clean_data.py (naming, file type, MRI, duplicates,
orientation) and in fix_problems.py (further problems of the cleaned delineations).

  split_name(filename)        name and extension, even a broken extension
  scan_key(filename)          'SUBC001_ses1' read from a badly written name
  read_nifti_bytes(path)      raw NIfTI bytes whatever the container (gzip, double gzip, zip, plain .nii)
  load(path)                  (raw bytes, nibabel image, voxels) or (None, None, None)
  get_labels(data)            non-zero integer values of a mask, None if it is not a mask (MRI)
  dice(a, b)                  Dice overlap of two boolean masks
  fix_orientation(img)        image reoriented to RAS, None if the grid is still wrong
"""

import gzip
import re
import zipfile
from pathlib import Path

import nibabel as nib
import numpy as np

EXPECTED_SHAPE = (192, 224, 224)      # grid of the base MRI
EXPECTED_VOXEL = (1.0, 1.0, 1.0)      # 1 mm isotropic


def split_name(filename):
    """Splits the name from its extension, even a broken one.
    'X_manual_seg.nii (1).gz' -> ('X_manual_seg', '.nii (1).gz'); 'X.docx' -> ('X', '.docx')."""
    m = re.search(r"[._]nii", filename)  # everything after the first '.nii' / '_nii' = extension
    if m:
        return filename[:m.start()], filename[m.start():]
    stem, dot, ext = filename.rpartition(".")
    return (stem, "." + ext) if dot else (filename, "")


def scan_key(filename):
    """Normalised scan 'SUBC001_ses1' read from a name, even a badly written one
    (SUBC20, SUBCO20, SUBJEC35, ses01, Session 2, S2...). '?' = unreadable part, None = no subject."""
    sub = re.search(r"SUB(?:JEC)?([CG]?)O?(\d+)", filename, re.I)
    ses = (re.search(r"(?:ses|session)[ _]?0*(\d)", filename, re.I)
           or re.search(r"[_-]S0*(\d)", filename))
    if not sub:
        return None
    group = sub.group(1).upper() or "?"
    session = ses.group(1) if ses else "?"
    return f"SUB{group}{int(sub.group(2)):03d}_ses{session}"


def read_nifti_bytes(path):
    """Raw (uncompressed) NIfTI content of the file whatever its extension:
    gzip (even misnamed), zip containing a .nii, or plain .nii. None if it is not a NIfTI."""
    raw = Path(path).read_bytes()
    if raw[:2] == b"PK":  # zip archive
        try:
            with zipfile.ZipFile(path) as z:
                members = [n for n in z.namelist() if ".nii" in n and not n.startswith("__MACOSX")]
                if len(members) != 1:
                    return None
                raw = z.read(members[0])
        except zipfile.BadZipFile:
            return None
    while raw[:2] == b"\x1f\x8b":  # one or more gzip layers
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError):
            return None
    is_nifti1 = raw[344:348] in (b"n+1\x00", b"ni1\x00")
    is_nifti2 = raw[4:8] in (b"n+2\x00", b"ni2\x00")
    return raw if (is_nifti1 or is_nifti2) else None


def load(path):
    """Loads the file. Returns (raw NIfTI bytes, nibabel image, voxels) or (None, None, None)."""
    raw = read_nifti_bytes(path)
    if raw is None:
        return None, None, None
    try:
        cls = nib.Nifti2Image if raw[4:8] in (b"n+2\x00", b"ni2\x00") else nib.Nifti1Image
        img = cls.from_bytes(raw)
        data = np.asarray(img.dataobj)
    except Exception:
        return None, None, None
    return raw, img, data


def get_labels(data):
    """Non-zero integer values present in the mask (None if it is not a mask)."""
    if data.dtype.kind == "f":
        if not np.allclose(data, np.round(data)):
            return None  # non-integer values = intensity image (MRI)
        data = data.round().astype(np.int64)
    return {int(v) for v in np.unique(data[data != 0])}  # only the non-zero voxels: much faster


def dice(a, b):
    total = a.sum() + b.sum()
    return 2 * np.logical_and(a, b).sum() / total if total else np.nan


def fix_orientation(img):
    """Reorients the image to RAS (voxel order + header; the real position of each voxel does not
    change). Returns the corrected image, or None if the grid is still wrong after reorientation
    (wrong size or wrong voxel size)."""
    canon = nib.as_closest_canonical(img)
    grid_ok = (len(canon.shape) == 3 and tuple(int(s) for s in canon.shape) == EXPECTED_SHAPE
               and np.allclose(canon.header.get_zooms()[:3], EXPECTED_VOXEL, atol=0.01))
    return canon if grid_ok else None
