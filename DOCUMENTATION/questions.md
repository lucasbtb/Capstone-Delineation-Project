# Open questions (to ask the supervisor)

## Data
1. **Sessions**: what do `ses1` / `ses2` mean? Two MRIs of the same subject (test-retest), or two delineations by the same rater?
2. **Labels 1–9**: which nucleus name matches each label? Is it one hemisphere or both?
3. **SUBC / SUBG**: are these really controls / patients? Which pathology is it?
4. **WMn**: some files contain "WMn". Is the base MRI a WMn-MPRAGE (white-matter-nulled, as for THOMAS)?
5. **Distribution**: why are some subjects delineated by several groups (e.g. C1–C4 in groups 1, 7, 8 and 16)? Is it on purpose, to measure inter-group agreement?
6. **Reference**: is there a reference segmentation (expert or automatic)?

## Problem files
7. Some files have labels outside 1–9 (10, 11, 12, 13, 35): a numbering mistake to remap, or files to exclude?
8. 15 "seg" files are actually intensity images (float32): the rater saved the MRI instead of the segmentation. Should these files be excluded or the segmentations asked for again?
9. Incomplete or empty files: should they be excluded?
10. Sessions `ses3`–`ses7` (rater 6j) and `ses9` (rater 9b): is it a naming mistake?

## Project
11. What is the exact goal: inter-rater and intra-rater agreement (Dice, volumes), C vs G comparison, something else?
