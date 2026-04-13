#!/bin/bash
set -e

PGDATA="/var/lib/postgresql/data"

echo "🔍 Démarrage de l'application..."

if [ ! -d "$PGDATA/base" ]; then
    echo "🚀 Initialisation de la base de données Aura Wealth..."
    
    # Appel direct grâce aux raccourcis globaux
    initdb -U postgres -D "$PGDATA"
    
    # Démarrage temporaire
    pg_ctl -D "$PGDATA" -w start
    
    echo "🔐 Configuration des accès SQL..."
    psql -U postgres -c "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';"
    psql -U postgres -c "CREATE DATABASE aura_db;"
    
    # Arrêt propre
    pg_ctl -D "$PGDATA" -m fast stop
fi

echo "✅ Prêt ! Lancement de l'Aura via Supervisord..."
exec /usr/bin/supervisord -c /app/supervisord.conf
