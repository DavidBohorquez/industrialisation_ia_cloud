# CLAUDE.md

## Projet

Notebook de machine learning (`notebooks/project_test_v1_final_final2.ipynb`, 64 cellules, commentaires et textes en français) qui prédit si une commande peut bénéficier d'une livraison express.

- Projet MLflow : `eligibilite-livraison-express`, version modèle `1.0.0`
- Variable cible : `express_eligible` (1 = éligible, 0 = non éligible)
- Les données sont synthétiques (`generate_orders_dataset`), le notebook est exécutable sans source externe.
- Le modèle est une aide à la décision et ne remplace pas les règles métier.

## Conventions

- Garder les textes du notebook et les commentaires en français.
- Installer les dépendances avec les cellules `%pip` du notebook : pandas, numpy, scikit-learn, matplotlib, seaborn, joblib, mlflow.
- Éditer le notebook via son JSON (ou un outil dédié) plutôt qu'à la main, pour préserver les sorties et les métadonnées.
