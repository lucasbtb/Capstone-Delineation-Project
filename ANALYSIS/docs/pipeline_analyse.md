# Pipeline d'analyse

Comment fonctionne la partie `ANALYSIS/`. Les règles à suivre sont dans `consigne_analyse.md` (rédigé par Lucas uniquement).

## Vue d'ensemble

```
DATA/DELINEATION_DATA  (brut, jamais modifié)
        │
        ├── 01_inventory.py  ──► RESULTS/01_inventory.csv   (état des lieux)
        │
        └── 02_easy_clean.py ──► DATA/CLEAN_DELINEATION     (problèmes 1–5 corrigés)
                             └─► RESULTS/02_easy_clean.csv  (journal : gardé / exclu, pourquoi)
```

Les deux scripts utilisent les **mêmes tests**, définis une seule fois dans `checks.py`.

## `checks.py` — définition des problèmes

Chaque test renvoie `(ok, détail)` : passe ou ne passe pas, et pourquoi.

| # | Problème | Fonction | Passe si… |
|---|---|---|---|
| 1 | Nommage | `test_naming` | nom (sans extension) = `SUB{C\|G}###_ses{1\|01\|2\|02}_Rater{Nx}_manual_seg`, et rater du nom = dossier |
| 2 | Extension | `test_extension` | extension `.nii.gz` et fichier réellement compressé gzip |
| 3 | Labels | `test_labels` | exactement les labels 1 à 9 (pas d'IRM, pas vide, aucun manquant ni en trop) |
| 4 | Doublons | `find_duplicates` | un seul fichier pour ce rater + scan ; sinon *copie exacte* (mêmes voxels) ou *contenu différent* |
| 5 | Orientation | `test_orientation` + `find_lr_flips` | grille 192×224×224 à 1 mm, header RAS, et masque non retourné gauche-droite par rapport aux autres raters du même scan |

Outils partagés :
- `build_inventory(dossier)` : applique les 5 tests à tout un dossier `Group N/Rater Nx/…` → une ligne par fichier.
- `passes(ligne, problèmes)` / `failed(ligne, problèmes)` : le fichier passe-t-il les tests choisis, et sinon lesquels.
- `load(chemin)` : lit le NIfTI quelle que soit l'extension (`.nii`, faux `.gz`, `.nii.gz.gz`, `.zip`).
- `fix_orientation(image)` : réoriente en RAS ; `None` si la grille reste incorrecte.
- `scan_key(nom)` / `clean_name(scan, rater)` : lire sujet + session dans un nom mal écrit, puis produire le nom final.

## `01_inventory.py` — état des lieux

Lecture seule. `RESULTS/01_inventory.csv` : une ligne par fichier brut, avec
- `<problème>_ok` et `<problème>_detail` pour chacun des 5 problèmes ;
- `errors` : toutes les erreurs du fichier en une phrase ;
- `all_ok` : passe les 5 tests.

## `02_easy_clean.py` — dossier propre

Corrige les problèmes 1 à 5 et écrit `DATA/CLEAN_DELINEATION` (vidé puis recréé à chaque `--apply`).

1. **Labels (3)** : fichier sans exactement les labels 1 à 9 → exclu.
2. **Orientation (5)** : header non RAS → réorienté en RAS ; mauvaise grille, ou masque retourné gauche-droite par rapport aux autres raters → exclu (on ne peut pas savoir si c'est un vrai retournement ou un mauvais scan).
3. **Nom (1)** : renommé `SUBC001_ses01_Rater1a_manual_seg.nii.gz` ; rater = dossier ; session hors 1–2 ou sujet illisible → exclu.
4. **Doublons (4)** : copies exactes → une seule gardée (le vrai `.nii.gz` en priorité) ; contenus différents tous valides → tous exclus.
5. **Extension (2)** : réécrit en vrai `.nii.gz`, contenu NIfTI identique.

Pour finir, le script relance les 5 tests sur `CLEAN_DELINEATION` et vérifie que chaque masque copié a exactement les mêmes voxels que l'original.

## Utilisation

```
python ANALYSIS/01_inventory.py           # état des lieux
python ANALYSIS/02_easy_clean.py          # simulation : journal seulement
python ANALYSIS/02_easy_clean.py --apply  # crée CLEAN_DELINEATION + vérification
```

## Pas encore traité (étapes futures)

Problèmes connus que les tests 1–5 ne voient pas (détail dans `potential_problem.md`) :
- scans mal assignés, repérables par l'origine du header (16i SUBC002–004_ses2 = SUBG002–004_ses2, 6j, 9b, 10j, 7c) ;
- masque identique chez deux raters différents (14c / 14i, SUBG009_ses2) ;
- labels probablement permutés (8 ↔ 9), contrôles anatomiques (volumes, hémisphères, composantes).
