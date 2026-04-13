#!/bin/bash

# Initialisation Postgres s'il est vide
if [ ! -d "/var/lib/postgresql/data/base" ]; then
    su - postgres -c "/usr/lib/postgresql/15/bin/initdb -D /var/lib/postgresql/data"
    echo "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';" | su - postgres -c "postgres --single -D /var/lib/postgresql/data"
    
    # Création de la BDD et tables
    su - postgres -c "psql -c \"CREATE DATABASE aura_db;\""
fi

# Lance Supervisor qui gère Postgres et Streamlit
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
