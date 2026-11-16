# Never to be modified by an AI

Structure of the Analysis part of the project.
Here, we start with raw data with many different issues, and we make it slowly but surely more usable.

# Initial problems and `build_clean_data.py`

The data downloaded from the Google Drive is mislabeled, a mess, some of it is garbage etc...
To even be able to start considering further problems, we need a good base to start work on.

## Problems list

1. files are not named correctly (in multiple ways)
1. duplicate files
1. files are scans, not delineations
1. not sure that the axis is always correct

## Solution

The `build_clean_data.py` file takes in the file structure of the google drive that are in DELINEATION_DATA.
It makes a DELINEATION_CLEAN folder.
Organises it the following way:
  all the delineations are put in a folder corresponding to their scan (so one folder for each C/G ID, session number combination)They are renamed using the following convention
  '{G|C}_<ID>_{1|2}_<ratergroup>_<raterid>'
Raters who have no delineations are removed and the other raters are renumbered accordingly.
We make a dataframe which has the following columns:
index, filepath, scantype(G or C), delinationID, session number, raterID
unclear files are renamed
duplicates are handled

# Further problems and fix_problems.py

Now we work with the data in DATA/DELINEATIONS_CLEAN

## Problems 

1. ne pas garder les fichiers avec + ou - de nuclei
1. Check que le fichier a la bonne orientation gauche droite
1. Points parasites
1. Delineation incomplète 
1. Labels interchangés
1. Le rater a par erreur placé deux points très loin des nuclei
1. le rater s'est arreté en pleine délinéation
1. Il manque des frames 
1. (Délinéation décalée / mauvais scan)

## Solutions

For each of these problems, we define a function in fix_problems.py that iterates over all the delineations in delineations.csv (that should be all of them). It adds two columns in delineation.csv  with the problem name (shortened) like 'problem_name_flag' and the other like 'problem_name_fix'. It checks to see if that problem exists in that delineation. If it does, it flags it in the dataframe (True).  If it doesn't it does not flag it (False). Unless the argument no_changes=True, the function also fixes IN PLACE the issue with that delineation. It writes a string summarising its changes in the second column (standardised accross an issue). Saving the .csv and updating the files should be done at the same time to avoid out of syncness.

All the problem funcions can call helpers. All the problems functions should be idempotent
A main function exists in fix_problems.py that runs every other function.
Furthermore, all functions should be able to be ran also on a single delineation.


# Staple and staple.py

For each scan with three or more delineations, a file is created that:
- takes the clean delineations CLEAN_DELINEATIONS
- applies the staple algorithm to all the groups of delineations, thus producing a set of "reference delineations"
- saves that in DATA/STAPLE
- makes a report with statistics
- the report shall include a line about the problems that were ran or not at the point when staple.py was run
