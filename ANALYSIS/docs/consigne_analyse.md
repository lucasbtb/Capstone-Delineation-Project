# JAMAIS TOUCHE PAR UNE IA

Voici les consiges claires de la partie analyse

# Fichier 01_Inventory et checks.py
- Permet de generer un êtat des lieux des delinéations
- crée un csv avec toutes les délinéations et les erreurs que la délinéation a (ex mauvais nommage, mauvaise extension, pas assez ou trop de labels etc )
- crée une fonction de test de définition du problème qui ne passe ou pas pas que l'on réutilisera dans le reste du code 

## Liste de problèmes 

1. de nommage des fichiers
2. d'extension incorrecte
3. ne pas garder les fichiers avec + ou - de nuclei
4. Check si des doublons sont exactement des copies ou ont juste le même nom mais différent
5. Check que le fichier a la bonne orientation gauche droite
6. Points parasites
7. Delineation incomplète 
8. Labels interchangés


Problèmes potentiels a rajouter 
-  Le rater a par erreur placé deux points très loin des nuclei
- le rater s'est arreté en pleine délinéation
- Il manque des frames 
9. (Délinéation décalée / mauvais scan)

## Prises de décisions associées
4. ne pas utiliser ceux avec un nuclei différent de 9 A UPDATE

## build_clean_data.py - new version

Takes all the data in DELINEATION_DATA.
Makes a NEW_CLEAN_DELINATION folder.
Organises it the following way:
  all the delineations are put in a folder corresponding to their scan (so one folder for each C/G ID, session number combination)They are renamed using the following convention
  '{G|C}_<ID>_{1|2}_<ratergroup>_<raterid>'
Raters who have no delineations are removed and the other raters are renumbered accordingly.
A first dataframe is created that identifies each G|C_Id
We make a dataframe which has the following columns:
index, filepath, scantype(G or C), delinationID, session number, raterID
unclear files are renamed
duplicates are handled

# Fichier 03_Staple

For each scan with three or more delineations, a file is created that:
- takes the clean delineations from 02
- applies the staple algorithm to all the groups of delineations, thus producing a set of "reference delineations"
- saves that somewhere that makes sense
- makes a report with statistics

# Definition précise des problèmes 
6. 
Parametre du centre de la delineation et median = 
Parametre du dice moyen avec les autres raters pour supprimer ?

7. 
Paramètres : la distance au bloc principal (mm), la taille du morceau (voxels) et le nombre de morceaux.

8. 
A completeer
