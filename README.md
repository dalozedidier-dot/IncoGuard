FluxGuard audit fix bundle v1

Objectif
- Corriger generated_at_utc (valeur epoch 1970) dans les fluxguard_summary.json
- Rendre les summaries auditables en ajoutant les SHA256 des artefacts référencés quand ils existent dans le bundle
- Propager les paramètres effectifs du module VoidMark (runs, noise, seed) dans les summaries qui le référencent
- Optionnel: quantifier les flottants à l’écriture JSON pour neutraliser des micro-écarts inter Python et inter OS

Usage (post-traitement d'un dossier d'artefacts dézippé)
1) python tools/fluxguard_normalize_outputs.py /chemin/vers/artefacts
   Exemple: python tools/fluxguard_normalize_outputs.py ./_ci_out

2) Optionnel: python tools/fluxguard_quantize_json.py /chemin/vers/artefacts --ndigits 12

Notes
- Le normalizer ne modifie pas les fichiers voidmark_mark.json, il enrichit les summaries pour audit.
- Le normalizer n’invente pas de seed_base. Il reporte la seed telle qu’écrite par VoidMark.
- Si tu veux une seed unique et traçable, ajoute seed_requested et seed_effective au générateur et reporte les deux partout.
