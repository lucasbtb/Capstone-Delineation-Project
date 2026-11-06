# Problèmes des délinéations

## Format
- Fichier non NIfTI (.docx, .DS_Store)
- Mauvaise compression (.nii.gz.gz, faux .gz, .zip)
- .nii au lieu de .nii.gz
- IRM sauvegardée au lieu du masque (float32)
- Header incohérent avec l'IRM de base
- Origine du header différente des autres rendus du même scan (13 fichiers, 7 à 26 mm) → IRM réelle ≠ nom
- sform absent (sform_code = 0, 167 fichiers) ou qform_code = 2 (4j)
- Extension corrompue (.nii (1).gz, _nii.gz, .nii.zip)

## Arborescence
- Sous-dossier dans un dossier rater (Rater 3a/delineated/)

## Nommage
- Sujet mal écrit (SUBC20, SUBCO20, SUBJEC35, SUB008)
- Identifiant inexploitable (Sub 32- Final)
- Session mal écrite (ses01, Session1, S2, ses_2)
- Session impossible (ses3–ses7 chez 6j, ses9 chez 9b)
- Session illisible (SUBC041-S2rater13J)
- Rater absent ou mal écrit (i10, 10i, 13J, Rate8b, RATER16i)
- Mention « WMn » dans le nom (7c, 13f, 13k)
- Séparateurs non standard (espace, tiret, point)
- Suffixe non standard (manual, manuel, seg 2, INCOMPLETE)

## Assignation
- Mauvaise session
- Sujet non assigné
- Nom de scan faux, IRM identifiable par l'origine du header :
  16i SUBC002–004_ses2 = SUBG002–004_ses2 ; 6j ses2–ses7 = ses1 ; 9b ses9 = ses2 ;
  10j SUBC001_ses2 = SUBC020_ses2 ; 7c SUBC001_ses2 = SUBC049_ses1
- Scans assignés manquants
- Scan jamais délinéé (SUBC044_ses2) ou une seule fois
- Rater sans rendu
- Dossier absent de la table Excel / rater de l'Excel sans dossier
- Mauvais sujet délinéé sous le bon nom

## Doublons
- Même scan rendu plusieurs fois
- Même scan en .nii et .nii.gz (3a, 4h, 15a)
- Même fichier copié sous un autre nom
- Masque identique voxel à voxel chez deux raters (14c et 14i, SUBG009_ses2)

## Labels
- Masque vide ou quasi vide
- Labels manquants (délinéation incomplète)
- Labels hors 1–9
- Labels permutés entre noyaux (8 ↔ 9 probable dans 36 fichiers, à confirmer)
- Correspondance label ↔ noyau inconnue

## Anatomie
- Un seul hémisphère
- Masque hors du thalamus
- Volumes aberrants / asymétrie G-D
- Voxels isolés, composantes déconnectées, trous
- Délinéation sur quelques coupes seulement
- Noyaux mal positionnés entre eux
- Frontières en escalier

## Méthodologie
- Sens des sessions inconnu
- Effet groupe confondu avec l'effet sujet
- Une seule session délinéée pour 26 sujets sur 68 (test-retest impossible pour eux)
- Statut « Done » de l'Excel non fiable
