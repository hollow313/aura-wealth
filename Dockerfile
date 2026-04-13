FROM python:3.11-slim

# Installation des dépendances
RUN apt-get update && apt-get install -y \
    postgresql postgresql-contrib libldap2-dev libsasl2-dev gcc supervisor curl \
    && ln -sf /usr/lib/postgresql/*/bin/* /usr/local/bin/ \
    && rm -rf /var/lib/apt/lists/*

# CRÉATION DE L'UTILISATEUR 568 (INDISPENSABLE POUR TRUENAS)
RUN groupadd -g 568 apps && \
    useradd -u 568 -g 568 -m -s /bin/bash apps

WORKDIR /app

# On donne la propriété du dossier /app à l'utilisateur apps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R apps:apps /app && chmod +x entrypoint.sh

# On expose le port
EXPOSE 6871
ENTRYPOINT ["./entrypoint.sh"]
