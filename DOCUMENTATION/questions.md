# Questions ouvertes (à poser au superviseur)

## Données
1. **Sessions** : que signifient `ses1` / `ses2` ? Deux IRM du même sujet (test-retest), ou deux délinéations du même rater ?
2. **Labels 1–9** : quel nom de noyau correspond à chaque label ? Est-ce un seul hémisphère ou les deux ?
3. **SUBC / SUBG** : est-ce bien contrôles / patients ? De quelle pathologie s'agit-il ?
4. **WMn** : certains fichiers contiennent « WMn ». L'IRM de base est-elle une WMn-MPRAGE (white-matter-nulled, comme pour THOMAS) ?
5. **Répartition** : pourquoi certains sujets sont-ils délinéés par plusieurs groupes (ex. C1–C4 dans les groupes 1, 7, 8 et 16) ? Est-ce voulu, pour mesurer l'accord inter-groupes ?
6. **Référence** : existe-t-il une segmentation de référence (expert ou automatique) ?

## Fichiers problématiques
7. Certains fichiers ont des labels hors de 1–9 (10, 11, 12, 13, 35) : erreur de numérotation à remapper, ou fichiers à exclure ?
8. 15 fichiers « seg » sont en réalité des images d'intensité (float32) : le rater a sauvegardé l'IRM au lieu de la segmentation. Faut-il exclure ces fichiers ou redemander les segmentations ?
9. Fichiers incomplets ou vides : faut-il les exclure ?
10. Sessions `ses3`–`ses7` (rater 6j) et `ses9` (rater 9b) : est-ce une erreur de nommage ?

## Projet
11. Quel est l'objectif exact : accord inter-rater et intra-rater (Dice, volumes), comparaison C vs G, autre ?
