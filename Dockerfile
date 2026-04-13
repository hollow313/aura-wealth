FROM python:3.11-slim

# Installation des dépendances
RUN apt-get update && apt-get install -y \
    postgresql postgresql-contrib libldap2-dev libsasl2-dev gcc supervisor curl \
    && ln -sf /usr/lib/postgresql/*/bin/* /usr/local/bin/ \
    && rm -rf /var/lib/apt/lists/*

# CRÉATION DE L'UTILISATEUR 568 (TRUENAS)
RUN groupadd -g 568 apps && \
    useradd -u 568 -g 568 -m -s /bin/bash apps

# --- LE CORRECTIF EST ICI ---
# On crée le dossier système pour les sockets Postgres et on donne les droits à "apps"
RUN mkdir -p /var/run/postgresql && \
    chown -R apps:apps /var/run/postgresql && \
    chmod 775 /var/run/postgresql
# ---------------------------

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R apps:apps /app && chmod +x entrypoint.sh

EXPOSE 6871
ENTRYPOINT ["./entrypoint.sh"]
