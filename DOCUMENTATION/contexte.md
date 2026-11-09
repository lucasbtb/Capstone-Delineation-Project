# Contexte

## Données — `DATA/` (non versionné)
- `DELINEATION_DATA/` : segmentations manuelles brutes des **noyaux du thalamus**, 9 labels (1–9, 0 = fond). Ne pas modifier.
- `sTHOMAS_FILES/` : dossiers sTHOMAS du drive (vide pour l'instant).
- IRM de base : disponibles, à ajouter.

## Délinéations
- Arborescence : `Group N/Rater Nx/SUB{C|G}###_ses#_RaterNx_manual_seg.nii.gz`
- **Group** = équipe d'étudiants (16). **Rater** = un étudiant (a–k).
- `SUBC` = contrôle sain (HC), `SUBG` = glaucome.
- Dossier rater vide = travail non rendu (86).
- Volumes : 192×224×224, 1 mm isotrope, RAS.

## Documents fournis — `DOCUMENTATION/given_documents/`
- `excel_delineation.xlsx` : table maître des raters (groupe, type HC/Glaucoma/Mixed, scans assignés). Contient des noms et emails.
- `colors.md` : couleur de chaque noyau, dans l'ordre recommandé de délinéation.
- `naming.md` : convention de nommage des fichiers.

## Suivi
- Questions ouvertes : `DOCUMENTATION/questions.md`
- Problèmes des données : `ANALYSIS/docs/potential_problem.md`
- Scripts : `ANALYSIS/` (numérotés, ex. `01_inventory.py`) — fonctionnement : `ANALYSIS/docs/pipeline_analyse.md`
