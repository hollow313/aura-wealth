#!/bin/bash
set -e

PGDATA="/var/lib/postgresql/data"

echo "🌌 Aura Wealth - Démarrage du système..."

# Si le dossier est vide, on initialise
if [ ! -d "$PGDATA/base" ]; then
    echo "🚀 Création de la base de données pour l'utilisateur $(id -un)..."
    
    initdb -U postgres -D "$PGDATA"
    
    pg_ctl -D "$PGDATA" -w start
    
    psql -U postgres -c "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';"
    psql -U postgres -c "CREATE DATABASE aura_db;"
    
    pg_ctl -D "$PGDATA" -m fast stop
fi

echo "✅ Configuration terminée. Lancement d'Aura Wealth..."
exec /usr/bin/supervisord -c /app/supervisord.conf
