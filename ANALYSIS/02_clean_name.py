"""
02_clean_name.py — Copie les délinéations exploitables dans un dossier propre, bien nommées.

Approche itérative : chaque étape (= une catégorie de problème) ajoute des fichiers
au dossier propre. Un fichier non traité par aucune étape reste hors du dossier,
avec la raison dans le journal.

  Étape 1 — CORRECT : fichiers qui passent toutes les vérifications de 01_inventory
            (all_ok). Copiés tels quels, nom harmonisé au format final.
  Étape 2 — NOM     : fichiers dont le SEUL problème est le nom (contenu, format,
            taille, orientation OK, pas de doublon). Sujet et session lus dans le
            nom mal écrit (colonne 'scan' de 01_inventory), rater lu dans le dossier.

Nom final : SUB{C|G}###_ses0{1|2}_Rater{Nx}_manual_seg.nii.gz   (ex. SUBC001_ses01_Rater1a_manual_seg.nii.gz)

Entrée  : RESULTS/01_inventory.csv (lancer 01_inventory.py avant).
Sorties : DATA/CLEAN_DELINEATION/Group N/Rater Nx/...   (uniquement avec --apply)
          RESULTS/02_clean_name.csv : une ligne par fichier d'origine (étape, nouveau nom ou raison).

Ne modifie jamais DATA/DELINEATION_DATA : les fichiers sont COPIÉS, octet pour octet.
Usage : python ANALYSIS/02_clean_name.py            -> simulation, écrit seulement le journal
        python ANALYSIS/02_clean_name.py --apply    -> fait réellement les copies
"""

import csv
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "DATA" / "DELINEATION_DATA"
CLEAN = ROOT / "DATA" / "CLEAN_DELINEATION"
INVENTORY = ROOT / "RESULTS" / "01_inventory.csv"
LOG = ROOT / "RESULTS" / "02_clean_name.csv"

APPLY = "--apply" in sys.argv
VALID_SESSIONS = {"1", "2"}  # ses3–ses9 = erreurs de nommage, traitées plus tard

# Problèmes connus que 01_inventory ne détecte pas (voir docs/potential_problem.md).
# Exclus pour l'instant : leur contenu est bon mais le nom désigne le mauvais scan,
# ou l'auteur du masque est incertain. Clé = (rater, scan lu dans le nom).
KNOWN_ISSUES = {
    ("16i", "SUBC002_ses2"): "mauvais scan (= SUBG002_ses2)",
    ("16i", "SUBC003_ses2"): "mauvais scan (= SUBG003_ses2)",
    ("16i", "SUBC004_ses2"): "mauvais scan (= SUBG004_ses2)",
    ("6j", "SUBC041_ses2"): "mauvais scan (= SUBC041_ses1)",
    ("10j", "SUBC001_ses2"): "mauvais scan (= SUBC020_ses2)",
    ("7c", "SUBC001_ses2"): "mauvais scan (= SUBC049_ses1)",
    ("14c", "SUBG009_ses2"): "copie identique de 14i, auteur inconnu",
    ("14i", "SUBG009_ses2"): "copie identique de 14c, auteur inconnu",
}


def is_true(value):
    return value == "True"  # le CSV stocke les booléens en texte


def clean_name(scan, rater):
    """'SUBC001_ses1' + '1a' -> 'SUBC001_ses01_Rater1a_manual_seg.nii.gz'.
    Retourne None si le sujet ou la session n'est pas exploitable."""
    m = re.fullmatch(r"SUB([CG])(\d{3})_ses(\d)", scan or "")
    if not m or m.group(3) not in VALID_SESSIONS:
        return None
    return f"SUB{m.group(1)}{m.group(2)}_ses0{m.group(3)}_Rater{rater}_manual_seg.nii.gz"


def only_name_is_wrong(r):
    """Tout est bon sauf le nom."""
    return (not is_true(r["name_ok"]) and is_true(r["format_ok"]) and is_true(r["labels_ok"])
            and is_true(r["size_ok"]) and is_true(r["orientation_ok"])
            and not is_true(r["duplicate"]) and not is_true(r["lr_flip_suspect"]))


def why_not(r):
    """Raison pour laquelle aucune étape ne prend le fichier (pour le journal)."""
    reasons = []
    if not is_true(r["format_ok"]):
        reasons.append(f"format ({r['format_issue']})")
    if r["n_labels"] and not is_true(r["labels_ok"]):
        reasons.append(f"labels ({r['labels'] or 'vide'})")
    if is_true(r["duplicate"]):
        reasons.append("doublon")
    if r["shape"] and not is_true(r["size_ok"]):
        reasons.append("taille")
    if r["orientation"] and not is_true(r["orientation_ok"]):
        reasons.append("orientation")
    if is_true(r["lr_flip_suspect"]):
        reasons.append("gauche-droite suspect")
    if not reasons and clean_name(r["scan"], r["rater"]) is None:
        reasons.append(f"nom inexploitable (lu : {r['scan'] or 'rien'})")
    return " + ".join(reasons)


# ---------------------------------------------------------------- tri des fichiers
with open(INVENTORY, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

log = []
for r in rows:
    new = clean_name(r["scan"], r["rater"])
    known = KNOWN_ISSUES.get((r["rater"], r["scan"]))
    if known:
        log.append({"original": r["file"], "step": "non_traite", "new_file": "",
                    "reason": f"connu : {known}"})
        continue
    if is_true(r["all_ok"]) and new:
        step = "1_correct"
    elif only_name_is_wrong(r) and new:
        step = "2_nom"
    else:
        step, new = "non_traite", ""
    log.append({
        "original": r["file"],
        "step": step,
        "new_file": f"{r['group']}\\Rater {r['rater']}\\{new}" if new else "",
        "reason": "" if new else why_not(r),
    })

# Sécurité : deux fichiers ne doivent jamais arriver sous le même nouveau nom.
targets = Counter(e["new_file"] for e in log if e["new_file"])
for e in log:
    if e["new_file"] and targets[e["new_file"]] > 1:
        e["step"], e["reason"], e["new_file"] = "non_traite", "conflit de nom final", ""

# ---------------------------------------------------------------- copie
if APPLY:
    for e in log:
        if e["new_file"]:
            dst = CLEAN / e["new_file"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(RAW / e["original"], dst)  # copie à l'identique

LOG.parent.mkdir(exist_ok=True)
with open(LOG, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=log[0].keys())
    writer.writeheader()
    writer.writerows(log)

# ---------------------------------------------------------------- résumé
steps = Counter(e["step"] for e in log)
print(("COPIE EFFECTUÉE" if APPLY else "SIMULATION (rien copié, ajouter --apply)") + "\n")
print(f"Étape 1 - correct tel quel : {steps['1_correct']}")
print(f"Étape 2 - nom corrigé      : {steps['2_nom']}")
print(f"Non traités                : {steps['non_traite']}  / {len(log)}")
for reason, c in Counter(e["reason"] for e in log if e["step"] == "non_traite").most_common():
    print(f"   {c:3d}  {reason}")
print(f"\nJournal : {LOG.relative_to(ROOT)}")
if APPLY:
    print(f"Dossier propre : {CLEAN.relative_to(ROOT)}")
