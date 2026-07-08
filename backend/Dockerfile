# Nephro Brain API Server v2 - Cloud Run
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api_server.py .
COPY openevidence_client.py .
COPY scoring_calculators.py .
COPY clinical_pathways.py .
COPY drug_database.json .
COPY nhi_database.json .

ENV PORT=8080
EXPOSE 8080

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 300 api_server:app
