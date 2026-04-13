#!/bin/bash
set -e

# 1. Tentative de changement de propriétaire (on ignore l'erreur si ça échoue)
echo "🔍 Vérification des permissions..."
chown -R postgres:postgres /var/lib/postgresql/data || echo "⚠️ Note: Impossible de changer le propriétaire (ACL ZFS), on continue quand même..."

# 2. Initialisation de Postgres si le dossier est vide
if [ ! -d "/var/lib/postgresql/data/base" ]; then
    echo "🚀 Initialisation de la base de données..."
    # On force l'initdb même si le chown a échoué, tant qu'on a le droit d'écriture
    runuser -u postgres -- /usr/lib/postgresql/15/bin/initdb -D /var/lib/postgresql/data
    
    runuser -u postgres -- /usr/lib/postgresql/15/bin/pg_ctl -D /var/lib/postgresql/data -w start
    
    echo "🔐 Configuration du mot de passe..."
    runuser -u postgres -- psql -c "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';"
    runuser -u postgres -- psql -c "CREATE DATABASE aura_db;"
    
    runuser -u postgres -- /usr/lib/postgresql/15/bin/pg_ctl -D /var/lib/postgresql/data -m fast stop
fi

echo "✅ Démarrage des services Aura..."
exec /usr/bin/supervisord -c /app/supervisord.conf
