# JAMAIS TOUCHE PAR UNE IA

Voici les consiges claires de la partie analyse

# Fichier 01_Inventory 
- Permet de generer un êtat des lieux des delinéations
- crée un csv avec toutes les délinéations et les erreurs que la délinéation a (ex mauvais nommage, mauvaise extension, pas assez ou trop de labels etc )

# checks.py
- crée des fonctions de test qui définissent les problèmes que l'on réutilisera dans le reste du code 

## Liste de problèmes 

1. Fichier mal nommé
2. Extension incorrecte
3. Les fichiers ont + ou - de 9 nuclei
4. Check si il y a des doublons qui sont exactement des copies 
5. Check que le fichier a la bonne orientation gauchedroite
6. Points parasites
7. Delineation incomplète ( il manque une frame)
8. Labels interchangés


Problèmes potentiels a rajouter 
-  Le rater a par erreur placé deux points très loin des nuclei
- le rater s'est arreté en pleine délinéation
- Il manque des frames 
- (Délinéation décalée / mauvais scan)

# Fichier 02_Easy_Clean
Ce fichier devra corriger les problèmes 1 / 2 / 3 / 4 / 5 
le met dans CLEAN_DELINEATION


# Fichier 03_Staple

For each scan with three or more delineations, a file is created that:
- takes the clean delineations from 02
- applies the staple algorithm to all the groups of delineations, thus producing a set of "reference delineations"
- saves that somewhere that makes sense
- makes a report with statistics

# Definition précise des problèmes 

1.

2.

3. On veut pas etre dans la situation ou les 9 labels sont parfaits mais on a un label 10 avec un pixel par exemple

6. 
Parametre du centre de la delineation et median = 
Parametre du dice moyen avec les autres raters pour supprimer ?

7. 
Paramètres : la distance au bloc principal (mm), la taille du morceau (voxels) et le nombre de morceaux.

8. 
A completer


Things to do and change in architecture 
All the paths of the data will be contained in a dataframe, 

TO COMPLETE

We need one folder with all the scans(taken from the STHOMAS files and put into a new clear folder)

