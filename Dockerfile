FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    postgresql postgresql-contrib supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Configuration par défaut
ENV POSTGRES_PASSWORD=nexus_secure
ENV APP_PORT=6871

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 6871
ENTRYPOINT ["./entrypoint.sh"]
