#!/bin/bash
set -e

# 1. Gestion des permissions du dossier de données
# On s'assure que le dossier appartient bien à l'utilisateur postgres
chown -R postgres:postgres /var/lib/postgresql/data

# 2. Initialisation de Postgres si le dossier est vide
if [ ! -d "/var/lib/postgresql/data/base" ]; then
    echo "🚀 Initialisation de la base de données..."
    runuser -u postgres -- /usr/lib/postgresql/15/bin/initdb -D /var/lib/postgresql/data
    
    # Démarrage temporaire pour configurer l'utilisateur
    runuser -u postgres -- /usr/lib/postgresql/15/bin/pg_ctl -D /var/lib/postgresql/data -w start
    
    echo "🔐 Configuration du mot de passe et de la base..."
    runuser -u postgres -- psql -c "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';"
    runuser -u postgres -- psql -c "CREATE DATABASE aura_db;"
    
    # Arrêt du démarrage temporaire
    runuser -u postgres -- /usr/lib/postgresql/15/bin/pg_ctl -D /var/lib/postgresql/data -m fast stop
fi

# 3. Lancement de Supervisor (Correction du chemin du fichier conf)
echo "✅ Démarrage des services Aura..."
exec /usr/bin/supervisord -c /app/supervisord.conf
