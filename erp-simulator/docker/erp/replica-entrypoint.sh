#!/bin/sh
# Point d'entrée de la réplique PostgreSQL (service postgres-replica,
# docker-compose.replica.yml).
#
# Premier démarrage (pas de cluster dans $PGDATA) : clone le primaire avec
# pg_basebackup, puis démarre PostgreSQL en « hot standby ».
# Démarrages suivants : le clone existe, PostgreSQL reprend la réplication en
# streaming là où il s'était arrêté.
#
# -R (--write-recovery-conf) écrit standby.signal et primary_conninfo : le serveur
# démarre en standby, donc en lecture seule par construction (toute écriture échoue
# avec « cannot execute ... in a read-only transaction »).
# -X stream : les WAL produits pendant la copie sont transférés en parallèle, le clone
# est cohérent dès la fin de la copie.
set -eu

: "${PGDATA:?PGDATA doit être défini}"
PRIMARY_HOST="${PRIMARY_HOST:-postgres}"
PRIMARY_PORT="${PRIMARY_PORT:-5432}"
REPLICATION_USER="${REPLICATION_USER:-replicator}"
: "${REPLICATION_PASSWORD:?REPLICATION_PASSWORD doit être défini}"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    # Clone dans un répertoire temporaire, renommé seulement en cas de succès :
    # un clone interrompu ne peut pas être pris pour un cluster valide.
    staging="$PGDATA.clone"
    rm -rf "$staging"

    echo "réplique : attente du primaire $PRIMARY_HOST:$PRIMARY_PORT (TCP)"
    until pg_isready -q -h "$PRIMARY_HOST" -p "$PRIMARY_PORT"; do
        sleep 1
    done

    echo "réplique : copie du primaire (pg_basebackup)"
    if ! PGPASSWORD="$REPLICATION_PASSWORD" pg_basebackup \
        --host="$PRIMARY_HOST" --port="$PRIMARY_PORT" \
        --username="$REPLICATION_USER" --no-password \
        --pgdata="$staging" --write-recovery-conf --wal-method=stream \
        --checkpoint=fast; then
        echo "réplique : pg_basebackup a échoué. Si le volume du primaire existait avant" >&2
        echo "docker-compose.replica.yml, le rôle $REPLICATION_USER n'existe pas encore :" >&2
        echo "relancer 02-replication.sh sur le primaire (voir l'en-tête du fichier)." >&2
        exit 1
    fi

    rm -rf "$PGDATA"
    mv "$staging" "$PGDATA"
    echo "réplique : copie terminée"
fi

# Le cluster existe : l'entrypoint officiel saute initdb et lance le serveur.
exec docker-entrypoint.sh postgres -c hot_standby=on "$@"
