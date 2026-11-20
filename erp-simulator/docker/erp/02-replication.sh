#!/bin/sh
# Côté primaire de la réplique en lecture seule (docker-compose.replica.yml).
#
# Monté dans /docker-entrypoint-initdb.d/ : l'image postgres l'exécute une seule fois,
# au premier démarrage (volume vide), après 01-init.sql. Il :
#   1. crée le rôle de réplication (REPLICATION LOGIN, aucun droit sur les tables) ;
#   2. autorise ce rôle à se connecter en mode réplication : la ligne
#      « host all all all » ajoutée par l'image ne couvre pas les connexions de
#      réplication, qui exigent le mot-clé « replication » dans pg_hba.conf.
#
# Idempotent : on peut le relancer sur un volume déjà initialisé (voir l'en-tête de
# docker-compose.replica.yml).
set -e

REPLICATION_USER="${REPLICATION_USER:-replicator}"
if [ -z "${REPLICATION_PASSWORD:-}" ]; then
    echo "02-replication.sh : REPLICATION_PASSWORD est vide" >&2
    exit 1
fi

# Toutes les adresses pour le TP ; en production, restreindre à l'adresse de la réplique.
hba_line="host replication $REPLICATION_USER all scram-sha-256"
if ! grep -qxF "$hba_line" "$PGDATA/pg_hba.conf"; then
    echo "$hba_line" >> "$PGDATA/pg_hba.conf"
fi

# Variables psql (:'user', :"user") : pas d'injection, même si le mot de passe contient
# des guillemets. Le mot de passe est stocké en SCRAM (password_encryption par défaut).
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v user="$REPLICATION_USER" -v password="$REPLICATION_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I', :'user')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'user') \gexec
ALTER ROLE :"user" WITH LOGIN REPLICATION PASSWORD :'password';
SELECT pg_reload_conf();
SQL

echo "02-replication.sh : rôle $REPLICATION_USER prêt pour la réplication"
