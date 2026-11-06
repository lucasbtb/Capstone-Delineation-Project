# Problèmes des délinéations

## Format
- Fichier non NIfTI (.docx, .DS_Store)
- Mauvaise compression (.nii.gz.gz, faux .gz, .zip)
- .nii au lieu de .nii.gz
- IRM sauvegardée au lieu du masque (float32)
- Header incohérent avec l'IRM de base

## Nommage
- Sujet mal écrit (SUBC20, SUBCO20, SUBJEC35, SUB008)
- Session mal écrite (ses01, Session1, S2)
- Rater absent ou mal écrit
- Suffixe non standard (manual, manuel, seg 2, INCOMPLETE)

## Assignation
- Mauvaise session
- Sujet non assigné
- Scans assignés manquants
- Rater sans rendu
- Dossier absent de la table Excel / rater de l'Excel sans dossier
- Mauvais sujet délinéé sous le bon nom

## Doublons
- Même scan rendu plusieurs fois
- Même fichier copié sous un autre nom

## Labels
- Masque vide ou quasi vide
- Labels manquants (délinéation incomplète)
- Labels hors 1–9
- Labels permutés entre noyaux
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
- Statut « Done » de l'Excel non fiable
