# 02_clean_name — Dossier propre des délinéations

**But** : réunir dans `DATA/CLEAN_DELINEATION/` toutes les délinéations exploitables, avec un nom uniforme.
Les données brutes ne sont jamais modifiées : les fichiers sont **copiés**.

**Nom final** : `SUBC001_ses01_Rater1a_manual_seg.nii.gz`

## Étapes
1. **Correct** : fichiers qui passent toutes les vérifications de `01_inventory` → copiés, nom harmonisé.
2. **Nom** : fichiers dont le seul problème est le nom → sujet et session relus dans le nom mal écrit, rater pris du dossier.
3. *(à venir)* une étape par catégorie de problème (format, doublons, scans mal assignés…).

## Règles
- Rater = toujours le nom du **dossier**.
- Seules les sessions 1 et 2 sont acceptées.
- Deux fichiers ne peuvent pas recevoir le même nom final (sinon : non traité).
- Problèmes connus invisibles pour `01_inventory` (mauvais scan, copie entre raters) : listés dans `KNOWN_ISSUES`, exclus pour l'instant.

## Utilisation
```
python ANALYSIS/01_inventory.py           # d'abord
python ANALYSIS/02_clean_name.py          # simulation : journal seulement
python ANALYSIS/02_clean_name.py --apply  # copie réelle
```
Journal : `RESULTS/02_clean_name.csv` — pour chaque fichier : étape, nouveau nom, ou raison du rejet.
