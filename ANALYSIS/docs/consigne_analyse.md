## JAMAIS TOUCHE PAR UNE IA

Voici les consiges claires de la partie analyse

Fichier 01_Inventory et checks.py
- Permet de generer un êtat des lieux des delinéations
- crée un csv avec toutes les délinéations et les erreurs que la délinéation a (ex mauvais nommage, mauvaise extension, pas assez ou trop de labels etc )
- crée une fonction de test de définition du problème qui ne passe ou pas pas que l'on réutilisera dans le reste du code 

# Liste de problèmes 

1. de nommage des fichiers
2. d'extension incorrecte
3. ne pas garder les fichiers avec + ou - de nuclei
4. Check si des doublons sont exactement des copies ou ont juste le même nom mais différent
5. Check que le fichier a la bonne orientation gauche droite

Problèmes potentiels a rajouter 
-  Le rater a par erreur placé deux points très loin des nuclei
- le rater s'est arreté en pleine délinéation
- Il manque des frames 

# Prises de décisions associées
4. ne pas utiliser ceux avec un nuclei différent de 9 A UPDATE

Fichier 02_Easy_Clean
Ce fichier devra corriger les problèmes 1 / 2 / 3 / 4 / 5 
le met dans CLEAN_DELINEATION

