# Viewer de délinéations

Page web **locale** pour comparer visuellement les délinéations d'un même sujet :
superposer, masquer, isoler les raters, filtrer par noyau, et voir l'accord (Dice).
Tout tourne dans le navigateur, sans serveur. Aucune donnée n'est envoyée en ligne.

---

## 1. Fichiers

| Fichier | Rôle |
|---|---|
| `ANALYSIS/viewer/build_viewer.py` | Lit les masques, prépare les données de la page |
| `ANALYSIS/viewer/delineation_io.py` | Lecture des NIfTI (y compris mal compressés) et lecture sujet/session dans les noms |
| `ANALYSIS/viewer/index.html` | Code de la page (modèle, recopié à chaque build) |
| `RESULTS/viewer/index.html` | **La page à ouvrir** (générée) |
| `RESULTS/viewer/data/*.js` | Données générées, un fichier par sujet (~27 Mo, ignoré par git) |
| `requirements.txt` | Paquets Python nécessaires |

Entrées lues (jamais modifiées) :
- `DATA/DELINEATION_DATA/`, les délinéations brutes ;
- `RESULTS/02_clean_name.csv`, le statut de chaque fichier, produit par `02_clean_name.py`.

---

## 2. Installation (une seule fois)

```bash
cd Capstone-Delineation-Project
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Sur Mac, ne pas utiliser `/opt/homebrew/bin/python3` directement : nibabel n'y est pas installé.
Dans VS Code, choisir `.venv` comme interpréteur (Cmd+Shift+P → *Python: Select Interpreter*).

---

## 3. Lancer

Ordre complet, à refaire quand les données ou le nettoyage changent :

```bash
.venv/bin/python ANALYSIS/01_inventory.py      # vérifications fichier par fichier -> RESULTS/01_inventory.csv
.venv/bin/python ANALYSIS/02_clean_name.py     # statut de chaque fichier          -> RESULTS/02_clean_name.csv
.venv/bin/python ANALYSIS/viewer/build_viewer.py   # données de la page (~1 min 30)
open RESULTS/viewer/index.html                 # ou double-clic dans le Finder
```

- Si seuls les statuts ont changé, il suffit de relancer `build_viewer.py`.
- Pour mettre à jour quelques sujets seulement : `build_viewer.py SUBC001 SUBG009`. Les autres sujets sont conservés.
- Après un nouveau build, un simple rechargement de la page suffit : les fichiers de données
  portent un numéro de version, donc le navigateur ne réutilise pas l'ancienne version en cache.

---

## 4. Utilisation

**En-tête**
- **Données** : choisit quelles délinéations sont visibles selon `02_clean_name.csv`.
  - *Propres* : étapes `1_correct` + `2_nom`, soit le contenu de `DATA/CLEAN_DELINEATION` (par défaut).
  - *Correctes* : étape `1_correct` seulement.
  - *Non traitées* : fichiers exclus par `02_clean_name`, avec la raison.
  - *Toutes* : tous les fichiers bruts lisibles.
- **Sujet** : n'affiche que les sujets qui ont au moins une délinéation sous le filtre, avec leur nombre.
- **Session** : ses1 / ses2 / toutes. Par défaut, la session qui a le plus de délinéations.
- **Affichage** : remplissage, contours, ou les deux.
- **Couleur** : *par délinéation* (une couleur par rater, le plus lisible pour comparer)
  ou *par noyau* (couleurs de `colors.md`).
- **Opacité**, **Zoom**, **Réticule**.

**Coupes**
Trois vues : axiale, coronale, sagittale.
- Clic ou glisser : déplacer le réticule.
- Molette ou curseur sous la vue : changer de coupe.
- Les coordonnées affichées sont celles du volume d'origine (voxels).

**Panneau de gauche**
- Une case par délinéation pour l'afficher ou la masquer. **solo** n'affiche qu'elle.
- Clavier : touches **1–9** pour basculer la n-ième délinéation, **Espace** pour inverser les visibles
  (utile pour alterner entre deux raters).
- **Noyaux** : n'afficher que certains labels. Le filtre s'applique aussi au Dice.

**Panneaux du bas**
- *Sous le curseur* : le label de chaque délinéation visible au voxel survolé.
- *Accord (Dice)* : avec 2 délinéations visibles, le Dice par noyau et la moyenne.
  Avec plus de 2, la matrice des Dice moyens.
  Le Dice compare **le même label** : si un rater a permuté deux labels, le Dice de ces noyaux tombe à ~0.

---

## 5. Les alertes affichées

Chaque délinéation porte un **badge** et parfois des messages en jaune. Ils ont **deux origines différentes**.

### a. Badge et texte à côté : `02_clean_name.py` (scripts de l'équipe)

Lus tels quels dans `RESULTS/02_clean_name.csv` :

| Badge | Signification |
|---|---|
| ✓ correct | `1_correct` : passe toutes les vérifications de `01_inventory` |
| ✓ nom corrigé | `2_nom` : seul le nom posait problème ; le nouveau nom est affiché après « → » |
| ✗ non traité | `non_traite` : exclu ; la raison est affichée à côté |
| ✗ hors journal | fichier introuvable dans `02_clean_name.csv` |

Raisons possibles, cumulées par « + » : `format (extension)`, `format (pas compressé)`,
`format (IRM au lieu du masque)`, `doublon` (même rater, même scan, plusieurs fichiers),
`labels (…)` (labels trouvés, si différents de 1–9), `taille`, `orientation`,
`gauche-droite suspect`, `nom inexploitable (lu : …)`, `conflit de nom final`, et
`connu : …` (problèmes repérés à la main, écrits dans `KNOWN_ISSUES` de `02_clean_name.py`).

### b. Lignes « ⚠ … » : calculées par `build_viewer.py`

| Alerte | Règle |
|---|---|
| nom non conforme | le nom ne respecte pas `SUB[CG]###_ses[0]1/2_RaterNx_manual_seg.nii.gz` (expression régulière reprise de `01_inventory.py`) |
| rater du nom ≠ dossier | nom conforme, mais le rater ne correspond pas au dossier |
| fichier mal compressé | lisible seulement après décompression manuelle (`.gz.gz`, `.zip`, faux `.gz`…) |
| labels : … | labels présents, s'ils sont différents de 1–9 |
| N voxels loin du thalamus (non affichés) | voir ci-dessous |

Les trois premières font en partie doublon avec le badge.

**« Voxels loin du thalamus »** : pour chaque sujet, on regroupe les voxels de **toutes** ses délinéations
(tous raters, toutes sessions). Sur chaque axe, on garde l'intervalle entre les percentiles 0,1 % et 99,9 %,
élargi de **12 voxels (12 mm)**. Les voxels hors de cette boîte sont comptés et **ne sont pas dessinés**.
- Au départ, cette boîte sert à recadrer l'affichage. Ce n'est pas un contrôle validé.
- Le compte est un **minimum** : un voxel parasite à l'intérieur de la boîte (entre les deux thalamus,
  dans un coin) n'est pas détecté.
- Ce contrôle n'existe ni dans `01_inventory` ni dans `02_clean_name`.
- Une méthode plus fiable serait les composantes connexes par label (`scipy.ndimage.label`).

---

## 6. Hypothèses faites

1. **Correspondance label ↔ noyau : supposée, probablement fausse.**
   On suppose label 1 = LGN, 2 = MGN, 3 = Pulvinar, 4 = AV, 5 = VA, 6 = VLA/VLP, 7 = VPL, 8 = MD, 9 = CM,
   d'après l'ordre de `given_documents/colors.md`. Or dans SUBC049 (rater 7a), le label 3 est
   ~15 mm **en avant** du label 4, alors que le pulvinar est postérieur et l'AV antérieur.
   Les noms de noyaux du viewer ne sont donc pas fiables. Les numéros de labels, eux, sont exacts.
2. **Orientation RAS, affichage en espace voxel.**
   Tous les fichiers déclarent RAS et font 192×224×224 à 1 mm. Les masques sont superposés
   **voxel à voxel**, sans tenir compte de l'origine du header. Convention neurologique :
   G à gauche de l'écran, D à droite ; axiale avec l'avant en haut ; sagittale avec l'avant à droite.
   Si un header est faux (cf. `potential_problem.md` : origines différentes de 7 à 26 mm),
   le viewer ne le corrige pas.
3. **Sujet et session.**
   - Fichiers propres : lus dans le **nom corrigé** par `02_clean_name.py`.
   - Autres fichiers : lus dans le nom d'origine, avec la même tolérance que `01_inventory.py`
     (`SUBC20`, `SUBCO20`, `ses01`, `S2`…).
   - Une lettre C/G manquante donne un sujet `SUB?###` (ex. « SUBJEC35 »), placé en fin de liste.
4. **Ce qui est affiché.** Tout fichier lisible contenant un masque d'entiers non vide.
   Les IRM sauvegardées à la place du masque, les masques vides, le `.docx` et `.DS_Store` ne sont jamais affichés.
5. **Correspondance avec le journal.** Les chemins sont comparés après normalisation :
   `\` remplacé par `/`, espaces retirés autour des noms de dossiers. En effet, `01_inventory.csv` a été
   généré sous Windows, qui supprime les espaces de `Group 16/ Rater 16i` et `Rater 3a/delineated `.

---

## 7. À savoir avant d'interpréter

- **Ne pas comparer ses1 et ses2 sur la même vue** : ce sont deux IRM différentes, non alignées.
  Le viewer l'indique et désactive le Dice dans ce cas.
- **Les mauvais scans connus apparaissent sous le sujet de leur nom**, donc le mauvais
  (ex. 16i `SUBC002_ses2` = en réalité `SUBG002_ses2`). Avec le filtre *Non traitées*, ils sont visiblement décalés
  par rapport aux autres raters.
- **Pas d'IRM de fond** : seuls les masques sont affichés (IRM pas encore dans `DATA/`).
- **Labels hors 1–9** (10, 11…) : affichés en blanc, sans nom de noyau.
- **Fichiers en `.nii`, `.gz.gz`, `.zip`** : décompressés **en mémoire** pour l'affichage.
  Aucun fichier de `DATA/` n'est modifié.
- **Couleurs par délinéation** : 8 couleurs ; au-delà de 8 délinéations, les couleurs se répètent.
  Comparer de préférence 2 ou 3 raters à la fois.

---

## 8. Dépannage

| Symptôme | Cause / solution |
|---|---|
| `ModuleNotFoundError: nibabel` | Script lancé avec le mauvais Python : utiliser `.venv/bin/python` |
| Page « Aucune donnée » | `build_viewer.py` pas encore lancé |
| « Données obsolètes pour … » | Fichier généré par une ancienne version : relancer `build_viewer.py`, puis Cmd+Shift+R |
| Sujet vide + avertissement de sessions | Ancien cache : Cmd+Shift+R |
| Tout est « ✗ hors journal » | `RESULTS/02_clean_name.csv` absent : lancer `02_clean_name.py` |
| Un sujet manque dans la liste | Aucune délinéation sous le filtre choisi : passer à *Toutes* |
