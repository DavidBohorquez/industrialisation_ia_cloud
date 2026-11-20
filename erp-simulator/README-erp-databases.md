# PostgreSQL, MongoDB et simulateur ERP

Le simulateur ERP est séparé de l'application `livraison_express_lite` :
`src/erp_simulator` joue le rôle d'un système externe qui alimente les bases.

Le code est organisé par responsabilité : `config.py` lit l'environnement,
`generator.py` produit les commandes, `storage.py` contient les adaptateurs de
bases et `simulator.py` orchestre le scénario via des contrats `Protocol`.

## Différences avec le sujet fourni

Ce dossier est le simulateur du TP4 (`tp4/`), importé tel quel puis corrigé.
Chaque écart avec le sujet est listé ici.

- **L'image se construit** : le `Dockerfile` copiait `src/erp_simulator/requirements.txt`,
  absent du sujet ; il utilise maintenant `requirements-databases.txt`.
- **`docker/erp/postgres-init.sql` existe** : `docker-compose.erp.yml` le monte mais il
  manquait. Le schéma reste créé par le simulateur (`PostgresWriter._ensure_schema`).
- **`.dockerignore`** en liste blanche : seuls les fichiers copiés par le `Dockerfile`
  entrent dans le contexte de build.
- `storage.py` : une ligne vide en trop retirée (règle `ruff` du dépôt), rien d'autre.
- Les fichiers `infrastructure/implementation/*_order_repository.py` cités plus bas ne
  font pas partie du sujet : c'est l'exercice du TP, réalisé dans l'application.
- **Cible `express_eligible` ajoutée** (section suivante) : `outcome.py`, colonne
  `express_eligible` (`SMALLINT`, `NULL` tant que le résultat n'est pas connu, migration
  2026 dans `schema_migrations`), champ `express_eligible` dans MongoDB, révélation après
  `LABEL_DELAY_DAYS` jours simulés.
- **Contrats dans `contracts.py`** : les `Protocol` quittent `storage.py`, pour que
  `simulator.py` ne dépende plus de psycopg et pymongo et se teste sans base.
- **MongoDB n'écrase plus une commande existante** : `UpdateOne` + `$setOnInsert` (insertion
  seulement si absente, comme `ON CONFLICT DO NOTHING` côté PostgreSQL) au lieu de
  `ReplaceOne`, qui effaçait le résultat déjà connu au redémarrage.
- **L'horloge simulée reprend après un redémarrage** : le premier lot live porte le
  lendemain de la commande la plus récente, au lieu de repartir d'aujourd'hui.
- **Rôle `ml_reader` en lecture seule** créé par `postgres-init.sql` (`SELECT` seulement,
  `default_transaction_read_only`) : le rôle utilisé par l'application (ADR-0009).

## Cible `express_eligible` (`outcome.py`)

Le sujet ne générait pas la cible : le professeur a confirmé l'oubli (2026-11-20) et
indiqué l'heuristique de génération du cours (notebook, cellule 8). `outcome.py` la
reprend avec les mêmes coefficients, la même sigmoïde et le même tirage (Bernoulli de
probabilité p), traduite dans le vocabulaire de l'ERP :

| Champ ERP | Valeur → pénalité ou bonus | Choix |
|---|---|---|
| `weather` | clear 0 · rain 0.10 · snow 0.25 · wind 0.20 | `wind` entre la pluie (0.10) et l'orage (0.30) |
| `delivery_zone` | centre 0 · suburb 0.175 · rural 0.45 | `suburb` au milieu de proche banlieue (0.10) et banlieue (0.25) |
| `customer_type` | individual 0 · business +0.15 | même bonus que `premium` |
| `carrier_capacity` | part libre = valeur / 50 | hypothèse : capacité libre sur un maximum de 50 |

Règles :

- même commande, même résultat, dans n'importe quel processus (graine `outcome:<order_id>`) ;
- un tirage aléatoire et non un seuil : sinon la cible serait une fonction exacte des
  variables et un modèle atteindrait ~100 % sans rien apprendre d'utile ;
- `preparation_time_min` à `NULL` (avant juillet 2017) : pas de résultat (`None`),
  car l'imputer fabriquerait une étiquette ;
- `weekend` à `NULL` (avant juillet 2015) : calculé depuis `day_of_week` ;
- valeur inconnue (par exemple `pluie`) ou capacité hors de 0-50 : `ValueError`.

Avec les distributions de l'ERP, environ 34 % des commandes sont éligibles, contre 79 %
avec les données du notebook : les distances y suivent une loi uniforme de 1 à 40 km.

### Quand le résultat est-il connu ?

Dans la réalité, on connaît le résultat d'une commande quelque temps après elle. Ici,
l'horloge est la date simulée la plus récente : chaque lot live avance d'un jour. Après
l'historique puis après chaque lot, le simulateur révèle le résultat des commandes datées
d'au moins `LABEL_DELAY_DAYS` jours simulés (2 par défaut) :

```
 lot             1        2        3        4        5
 date simulée  20 nov.  21 nov.  22 nov.  23 nov.  24 nov.
 résultats       -        -      20 nov.  21 nov.  22 nov.
```

Une commande live reste donc sans résultat pendant deux lots : c'est elle qu'un modèle
aurait à prédire. Les mises à jour ne touchent que les résultats encore `NULL`
(idempotentes) ; MongoDB est mis à jour sans upsert (les commandes d'avant 2023 n'y
existent pas). Pour suivre la révélation : `docker compose -f docker-compose.erp.yml logs
-f erp-simulator` (lignes « Résultats connus jusqu'au … »).

Tests : `pytest erp-simulator/tests` depuis la racine du dépôt (lancés aussi par la CI).

À savoir : `LIVE_ORDER_LIMIT` est le **dernier numéro de séquence** du flux live, pas un
nombre de commandes. Avec l'historique par défaut (10 000 + 1 000 commandes), le flux
live commence à `ERP-00011001` : `LIVE_ORDER_LIMIT=200` ne produit donc aucune commande.

Par défaut, PostgreSQL reçoit des commandes historiques réparties entre le
1er janvier 2015 et hier. MongoDB reçoit les mêmes commandes historiques que
PostgreSQL pour la période 2023 -> hier. Les deux bases reçoivent ensuite les
mêmes commandes courantes à partir d'aujourd'hui.
Le scénario est simulé : le premier lot live porte la date du jour de départ,
le deuxième lot porte la date du lendemain, puis le jour suivant, sans attendre
le calendrier réel. Les dates futures sont donc volontaires dans ce jeu de test.

Toutes les commandes utilisent le même identifiant séquentiel dans les deux bases,
par exemple `ERP-00011001`. L'identifiant ne contient pas la date et reste unique
entre l'ancien historique, l'historique partagé et le flux live.

L'historique reproduit aussi les migrations : `weekend` vaut `NULL` avant le
1er juillet 2015, et `preparation_time_min` vaut `NULL` avant le 1er juillet
2017. Les commandes à partir d'aujourd'hui possèdent toutes les colonnes
renseignées.

Les logs indiquent les connexions, le lot en cours, le nombre de lignes PostgreSQL
effectivement insérées et le résultat de l'upsert MongoDB. Pour les suivre :

```bash
docker compose -f docker-compose.erp.yml logs -f erp-simulator
```

Le niveau de log est configurable avec `LOG_LEVEL=DEBUG`, `INFO`, `WARNING` ou
`ERROR`.

Ce dossier propose deux implémentations du contrat `OrderRepository` :

- `infrastructure/implementation/postgres_order_repository.py` avec `PostgresOrderRepository` ;
- `infrastructure/implementation/mongo_order_repository.py` avec `MongoOrderRepository`.

## Démarrer les bases et le simulateur ERP

Depuis le dossier `erp-simulator` :

```bash
docker compose -f docker-compose.erp.yml up --build
```

Le simulateur publie un lot de commandes toutes les cinq secondes dans les deux
bases. Les réglages sont modifiables sans changer le code :

```bash
BATCH_SIZE=20 INTERVAL_SECONDS=10 docker compose -f docker-compose.erp.yml up --build
```

Le volume est configurable. Mettre une valeur à `0` rend le flux correspondant
illimité ; une valeur positive le borne :

```bash
POSTGRES_HISTORY_ORDERS=100 RECENT_HISTORY_ORDERS=50 LIVE_ORDER_LIMIT=200 \
  docker compose -f docker-compose.erp.yml up --build
```

`POSTGRES_HISTORY_ORDERS` contrôle l'ancien historique PostgreSQL (2015-2022),
et `RECENT_HISTORY_ORDERS` contrôle le jeu partagé 2023 -> hier écrit dans les
deux bases. Pour désactiver complètement un historique, utiliser
`POSTGRES_HISTORY_ORDERS=0` ou `RECENT_HISTORY_ORDERS=0`.

Arrêter les conteneurs sans perdre les données :

```bash
docker compose -f docker-compose.erp.yml down
```

Réinitialiser les données (action volontairement destructive) :

```bash
docker compose -f docker-compose.erp.yml down -v
```

## Utiliser les repositories depuis Python

Installer les dépendances complémentaires :

```bash
pip install -r requirements-databases.txt
```