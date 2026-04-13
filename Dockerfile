FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    postgresql postgresql-contrib libldap2-dev libsasl2-dev gcc supervisor curl \
    # Astuce : On crée des raccourcis globaux pour Postgres (version 15, 16, etc.)
    && ln -sf /usr/lib/postgresql/*/bin/* /usr/local/bin/ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV APP_PORT=6871
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 6871
ENTRYPOINT ["./entrypoint.sh"]
