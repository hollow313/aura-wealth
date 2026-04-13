#!/bin/bash
set -e

# Dossier de données Postgres
PGDATA="/var/lib/postgresql/data"

echo "🔍 Vérification des accès pour l'utilisateur $(id -u)..."

# On tente le chown mais on ne stoppe pas le script si ça échoue (erreur 1)
chown -R postgres:postgres "$PGDATA" 2>/dev/null || echo "⚠️ Note: ACL ZFS détectées, passage outre le chown."

# Si le dossier est vide, on initialise la DB
if [ ! -d "$PGDATA/base" ]; then
    echo "🚀 Initialisation de la base de données Aura Wealth..."
    
    # On initialise en tant qu'utilisateur postgres
    runuser -u postgres -- /usr/lib/postgresql/15/bin/initdb -D "$PGDATA"
    
    # Démarrage temporaire pour configurer les accès
    runuser -u postgres -- /usr/lib/postgresql/15/bin/pg_ctl -D "$PGDATA" -w start
    
    echo "🔐 Configuration des accès SQL..."
    runuser -u postgres -- psql -c "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';"
    runuser -u postgres -- psql -c "CREATE DATABASE aura_db;"
    
    # Arrêt propre
    runuser -u postgres -- /usr/lib/postgresql/15/bin/pg_ctl -D "$PGDATA" -m fast stop
fi

echo "✅ Prêt ! Lancement de l'Aura via Supervisord..."
exec /usr/bin/supervisord -c /app/supervisord.conf
