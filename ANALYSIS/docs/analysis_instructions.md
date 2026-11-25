# Never to be modified by an AI

Structure of the Analysis part of the project.
Here, we start with raw data with many different issues, and we make it slowly but surely more usable.

General rules  
- DATA/DELINEATION_DATA (raw data) is never modified.
- The viewer shows the delineations as they really are and never alters the data before showing it.


# Initial problems and `build_clean_data.py`

The data downloaded from the Google Drive is mislabeled, a mess, some of it is garbage etc...
To even be able to start considering further problems, we need a good base to start work on.

## Problems list

-  files are not named correctly : the name does not follow DOCUMENTATION/given_documents/naming.md
-  wrong file extension: the file is not a real .nii.gz
-  duplicate files : same rater, same scan
-  files are scans, not delineations
- checks for the right orientation = RAS

## Solution

The `build_clean_data.py` file takes in the file structure of the google drive that are in DELINEATION_DATA.
It makes a DELINEATION_CLEAN folder.
Organises it the following way:
  all the delineations are put in a folder corresponding to their scan (so one folder for each C/G ID, session number combination). 
Raters who have no delineations are removed and the other raters are renumbered accordingly.
We make a dataframe which has the following columns:
index, filepath, scantype(G or C), delineationID, session number, raterID

How each problem is fixed :
- Naming: the name is corrected if all the information is in the old name (or known from the team: NAME_FIXES). 
- Extension: converted to .nii.gz if the content is a readable NIfTI. Otherwise not copied.
- Duplicates: if two files are identical voxel by voxel, only one is kept.
- Scans instead of delineations: not copied.
- If the file is not RAS, it rearranges the voxels into RAS order. The delineation itself is unchanged, only the storage order changes.

Report: RESULTS/build_clean_data_report.csv explains clearly what happened to each raw file:
kept or not copied, which problem, what was done (name corrected, old extension, converted...), and the new file it became.



# Further problems and fix_problems.py

Now we work with the data in DATA/DELINEATIONS_CLEAN

## Problems 

3. Delineation has more than 9 nuclei
4. Delineation has less than 9 nuclei
1. Stray points: small pieces separated from the nuclei
1. Swapped labels: the label numbers do not match the nuclei / colours of DOCUMENTATION/given_documents/colors.md
5. Les couleurs associées a chaque label ne correspondent pas au couleur de DCOUMENTATION/given_documents/colors.md
1. Incomplete delineation (missing frame)
1. The rater placed points very far from the nuclei by mistake
1. The rater stopped halfway through the delineation
1. Shifted delineation / wrong scan

## Solutions

For each of these problems, we define a function in fix_problems.py that iterates over all the delineations in delineations.csv (that should be all of them). It adds two columns in delineation.csv  with the problem name (shortened) like 'problem_name_flag' and the other like 'problem_name_fix'. It checks to see if that problem exists in that delineation. If it does, it flags it in the dataframe (True).  If it doesn't it does not flag it (False). Unless the argument no_changes=True, the function also fixes IN PLACE the issue with that delineation. It writes a string summarising its changes in the second column (standardised accross an issue). Saving the .csv and updating the files should be done at the same time to avoid out of syncness.

All the problem funcions can call helpers. All the problems functions should be idempotent
A main function exists in fix_problems.py that runs every other function.
Furthermore, all functions should be able to be ran also on a single delineation.

1) solution 1 ...


# Staple and staple.py

For each scan with three or more delineations, a file is created that:
- takes the clean delineations CLEAN_DELINEATIONS
- applies the staple algorithm to all the groups of delineations, thus producing a set of "reference delineations"
- saves that in DATA/STAPLE
- makes a report with statistics
- the report shall include a line about the problems that were ran or not at the point when staple.py was run

