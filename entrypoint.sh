#!/bin/bash
set -e

PGDATA="/var/lib/postgresql/data"

echo "🔍 Démarrage en tant qu'utilisateur $(id -un) (UID: $(id -u))..."

# Si le dossier est vide, l'utilisateur 568 initialise la DB lui-même !
if [ ! -d "$PGDATA/base" ]; then
    echo "🚀 Initialisation de la base de données Aura Wealth..."
    
    # On force la création de l'utilisateur interne "postgres"
    /usr/lib/postgresql/15/bin/initdb -U postgres -D "$PGDATA"
    
    # Démarrage temporaire
    /usr/lib/postgresql/15/bin/pg_ctl -D "$PGDATA" -w start
    
    echo "🔐 Configuration des accès SQL..."
    # On exécute psql directement
    psql -U postgres -c "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';"
    psql -U postgres -c "CREATE DATABASE aura_db;"
    
    # Arrêt propre
    /usr/lib/postgresql/15/bin/pg_ctl -D "$PGDATA" -m fast stop
fi

echo "✅ Prêt ! Lancement de l'Aura via Supervisord..."
exec /usr/bin/supervisord -c /app/supervisord.conf
