# Viewer de délinéations

Page web **locale** avec deux usages :
1. **Comparer les raters** d'un même sujet : superposer, masquer, isoler, filtrer par label, voir l'accord (Dice).
2. **Détecter des erreurs** pas encore couvertes par l'analyse (points parasites, délinéation incomplète,
   coupes manquantes, volumes anormaux), les **noter**, puis exporter les notes pour les reporter dans la consigne
   et les corriger ensuite dans `checks.py` / `02_easy_clean.py`.

Tout tourne dans le navigateur, sans serveur. Aucune donnée n'est envoyée en ligne.

**Usage rapide** : choisir un sujet → cliquer sur une délinéation à gauche → lire ses alertes dans
le panneau *Contrôles* → bouton **aller** pour voir le problème sur les coupes → écrire une note →
**Exporter les notes** en haut à droite.

---

## 1. Fichiers

| Fichier | Rôle |
|---|---|
| `ANALYSIS/viewer/build_viewer.py` | Lit les masques (avec `ANALYSIS/checks.py`, comme l'analyse), prépare les données de la page |
| `ANALYSIS/viewer/index.html` | Code de la page (modèle, recopié à chaque build) |
| `RESULTS/viewer/index.html` | **La page à ouvrir** (générée) |
| `RESULTS/viewer/data/*.js` | Données générées, un fichier par sujet (~27 Mo, ignoré par git) |
| `requirements.txt` | Paquets Python nécessaires |

Entrées lues (jamais modifiées) :
- `DATA/DELINEATION_DATA/`, les délinéations brutes ;
- `RESULTS/01_inventory.csv`, les erreurs de chaque fichier, produit par `01_inventory.py` ;
- `RESULTS/02_easy_clean.csv`, le statut de chaque fichier (gardé / exclu), produit par `02_easy_clean.py`.

Fonctionnement de l'analyse elle-même : `ANALYSIS/docs/pipeline_analyse.md`.

---

## 2. Installation (une seule fois)

```bash
cd Capstone-Delineation-Project
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Sur Windows, remplacer `.venv/bin/` par `.venv\Scripts\` dans toutes les commandes.
Sur Mac, ne pas utiliser `/opt/homebrew/bin/python3` directement : nibabel n'y est pas installé.
Dans VS Code, choisir `.venv` comme interpréteur (Cmd+Shift+P → *Python: Select Interpreter*).

---

## 3. Lancer

Ordre complet, à refaire quand les données ou le nettoyage changent :

```bash
.venv/bin/python ANALYSIS/01_inventory.py          # 5 tests par fichier       -> RESULTS/01_inventory.csv
.venv/bin/python ANALYSIS/02_easy_clean.py --apply # statut gardé / exclu       -> RESULTS/02_easy_clean.csv
.venv/bin/python ANALYSIS/viewer/build_viewer.py   # données de la page + contrôles (~1 min 30 Mac, ~5 min Windows)
open RESULTS/viewer/index.html                 # ou double-clic dans le Finder
```

Sur Windows (PowerShell) : `.venv\Scripts\python ANALYSIS\viewer\build_viewer.py` puis `start RESULTS\viewer\index.html`.

- Si seuls les statuts ont changé, il suffit de relancer `build_viewer.py`.
- Pour mettre à jour quelques sujets seulement : `build_viewer.py SUBC001 SUBG009`. Les autres sujets sont conservés.
- Après un nouveau build, un simple rechargement de la page suffit : les fichiers de données
  portent un numéro de version, donc le navigateur ne réutilise pas l'ancienne version en cache.

---

## 4. Utilisation

**En-tête**
- **Données** : choisit quelles délinéations sont visibles selon `02_easy_clean.csv`.
  - *Propres* : fichiers gardés, soit le contenu de `DATA/CLEAN_DELINEATION` (par défaut).
  - *Sans correction* : gardés tels quels (passent les 5 tests de `01_inventory`).
  - *Exclues* : fichiers exclus par `02_easy_clean`, avec la raison.
  - *Toutes* : tous les fichiers bruts lisibles.
- **Sujet** : n'affiche que les sujets qui ont au moins une délinéation sous le filtre, avec leur nombre.
- **Session** : ses1 / ses2 / toutes. Par défaut, la session qui a le plus de délinéations.
- **Exporter les notes** : télécharge `notes_viewer.csv` (toutes les notes, tous sujets).
- **Réglages** (menu) :
  - *Affichage* : remplissage, contours, ou les deux ;
  - *Couleur* : *par délinéation* (une couleur par rater, le plus lisible pour comparer)
    ou *par label* (couleurs de `colors.md`) ;
  - *Opacité*, *Zoom*, *Réticule*.

**Coupes**
Trois vues : axiale, coronale, sagittale.
- Clic ou glisser : déplacer le réticule.
- Molette ou curseur sous la vue : changer de coupe.
- Les coordonnées affichées sont celles du volume d'origine (voxels).

**Panneau de gauche**
- **Case** : afficher / masquer la délinéation. **solo** n'affiche qu'elle.
- **Clic sur la ligne** : la sélectionne (cadre bleu) et affiche ses contrôles dans le panneau *Contrôles*.
- Chaque ligne résume ses alertes : ⚠ orange = erreurs de `01_inventory.csv`, ● rouge = contrôles du viewer
  (● vert = aucune alerte). 📝 = une note existe.
- Clavier : touches **1–9** pour basculer la n-ième délinéation, **Espace** pour inverser les visibles
  (utile pour alterner entre deux raters).
- **Labels** : n'afficher que certains labels (affichés par numéro **L1–L9** ; le nom de noyau supposé
  apparaît au survol). Le filtre s'applique aussi au Dice.

**Panneau *Contrôles*** (délinéation sélectionnée)
- Tableau par label et par côté : voxels, médiane des autres raters, fragments isolés / détachés, trous.
  Les cases en rouge sont à regarder.
- Liste des **fragments** et des **trous** : le bouton **aller** place le curseur dessus et l'entoure en jaune.
- **Note** : texte libre, enregistré automatiquement (voir § 5c).

**Vue d'ensemble** : les délinéations visibles projetées sur le **volume entier**. Le cadre en pointillés
correspond aux coupes du haut ; les voxels hors de ce cadre sont dessinés en **rouge** (agrandis pour rester visibles).
Un clic dans le cadre déplace le curseur.

**Panneaux du bas**
- *Sous le curseur* : le label de chaque délinéation visible au voxel survolé.
- *Accord (Dice)* : avec 2 délinéations visibles, le Dice par label et la moyenne.
  Avec plus de 2, la matrice des Dice moyens.
  Le Dice compare **le même label** : si un rater a permuté deux labels, le Dice de ces labels tombe à ~0.
  Un Dice à 0 partout = délinéations décalées (mauvais scan, header différent).

---

## 5. Les alertes affichées

Chaque délinéation porte un **badge**, un texte à côté et parfois des lignes « ⚠ ».

### a. Badge et texte : `RESULTS/02_easy_clean.csv`

| Badge | Signification | Texte affiché |
|---|---|---|
| ✓ propre | gardé tel quel, passe les 5 tests | — |
| ✓ corrigé | gardé après correction ; nouveau nom après « → » | corrections faites (renommé, converti en .nii.gz, doublon…) |
| ✗ exclu | absent de `CLEAN_DELINEATION` | raison de l'exclusion (labels, nom inexploitable, doublon, orientation) |
| ✗ hors journal | fichier introuvable dans `02_easy_clean.csv` | — |

### b. Lignes « ⚠ … »

- Les erreurs du fichier **brut**, telles que dans la colonne `errors` de `RESULTS/01_inventory.csv`
  (`naming: …`, `extension: …`, `labels: …`, `duplicate: …`, `orientation: …`).
  Pour un fichier *corrigé*, ce sont donc les erreurs d'origine, réparées dans `CLEAN_DELINEATION`.
### c. Contrôles du viewer (● rouge) : calculés par `build_viewer.py`

Contrôles **exploratoires**, pour repérer des problèmes. Ils n'existent ni dans `01_inventory` ni dans
`02_easy_clean` : un problème confirmé à l'œil est à reporter dans la consigne, puis à ajouter à `checks.py`.

Chaque label est **bilatéral** : normalement un bloc à gauche et un bloc à droite. Pour chaque label :
1. On sépare le masque en **morceaux** (composantes connexes, 26-connexité : deux voxels qui se touchent
   même par un coin font partie du même morceau).
2. Chaque morceau est attribué à un **côté** selon sa position par rapport au centre gauche-droite de la délinéation.
3. Sur chaque côté, le plus gros morceau est le **bloc principal** ; les autres sont des **fragments** :
   - **isolé** : à plus de 3 mm du bloc principal → point parasite probable (compté dans l'alerte) ;
   - **détaché** : à 3 mm ou moins → souvent une coupe sautée ou un coup de pinceau (détail seulement).
4. **Trous entre coupes** : sur chaque axe, coupe vide entre la première et la dernière coupe du label
   (bloc principal + fragments détachés). Signe probable d'une **coupe oubliée** (« frame manquante »).
5. **Volume anormal** : voxels du label sur ce côté < 50 % ou > 200 % de la **médiane** des délinéations
   de la même session sous le filtre courant (au moins 3 délinéations). Signe possible d'une délinéation
   **arrêtée en cours**, d'un label oublié ou de labels permutés.
6. **Hors cadre** : le cadre des coupes est calculé pour chaque sujet sur **toutes** ses délinéations
   (percentiles 0,1 %–99,9 % sur chaque axe, + 12 mm). Les voxels hors cadre ne peuvent pas être montrés sur
   les coupes : ils apparaissent **en rouge dans la vue d'ensemble**.

Limites :
- Le côté est estimé par position : un fragment qui déborde la ligne médiane peut être compté du mauvais côté.
- Un label délinéé d'un seul côté donne un volume « absent » de l'autre côté (c'est voulu).
- Sur les premières données (373 délinéations propres) : 162 ont au moins un fragment isolé, 127 un trou
  et 86 des voxels hors cadre. Beaucoup de fragments isolés font 1 voxel : à trier à l'œil avant d'en faire une règle.

### d. Notes

- Une note par délinéation (panneau *Contrôles*), enregistrée automatiquement **dans ce navigateur**
  (`localStorage`) : elle n'est pas dans le projet et peut être perdue (navigation privée, cache vidé,
  autre navigateur ou autre ordinateur).
- **Exporter les notes** régulièrement : `notes_viewer.csv` (sujet, session, groupe, rater, fichier, statut, note, date).
- Les notes restent après un nouveau build : elles sont rattachées au chemin du fichier brut.

---

## 6. Hypothèses faites

1. **Correspondance label ↔ noyau : supposée, probablement fausse.**
   On suppose label 1 = LGN, 2 = MGN, 3 = Pulvinar, 4 = AV, 5 = VA, 6 = VLA/VLP, 7 = VPL, 8 = MD, 9 = CM,
   d'après l'ordre de `given_documents/colors.md`. Or dans SUBC049 (rater 7a), le label 3 est
   ~15 mm **en avant** du label 4, alors que le pulvinar est postérieur et l'AV antérieur.
   C'est pourquoi le viewer affiche les labels par **numéro** (L1–L9) ; le nom supposé n'apparaît qu'au survol.
2. **Orientation RAS, affichage en espace voxel.**
   Tous les fichiers déclarent RAS et font 192×224×224 à 1 mm. Les masques sont superposés
   **voxel à voxel**, sans tenir compte de l'origine du header. Convention neurologique :
   G à gauche de l'écran, D à droite ; axiale avec l'avant en haut ; sagittale avec l'avant à droite.
   Si un header est faux (cf. `potential_problem.md` : origines différentes de 7 à 26 mm),
   le viewer ne le corrige pas.
3. **Sujet et session.**
   - Fichiers gardés : lus dans le **nom corrigé** par `02_easy_clean.py`.
   - Autres fichiers : lus dans le nom d'origine, avec `scan_key` de `checks.py`
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
  (ex. 16i `SUBC002_ses2` = en réalité `SUBG002_ses2`). Seul 16i `SUBC002_ses2` est exclu (retournement gauche-droite
  suspect) ; les autres sont pour l'instant dans *Propres*, visiblement décalés par rapport aux autres raters.
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
| `ModuleNotFoundError: nibabel` ou `scipy` | Script lancé avec le mauvais Python : utiliser `.venv/bin/python`, ou relancer `pip install -r requirements.txt` |
| Page « Aucune donnée » | `build_viewer.py` pas encore lancé |
| « Données obsolètes pour … » | Fichier généré par une ancienne version : relancer `build_viewer.py`, puis Cmd+Shift+R (Ctrl+Shift+R sous Windows) |
| Notes disparues | Autre navigateur, navigation privée ou cache vidé : les notes sont dans le navigateur, d'où l'export CSV |
| Sujet vide + avertissement de sessions | Ancien cache : Cmd+Shift+R |
| Tout est « ✗ hors journal » | `RESULTS/02_easy_clean.csv` absent : lancer `02_easy_clean.py` |
| Un sujet manque dans la liste | Aucune délinéation sous le filtre choisi : passer à *Toutes* |
