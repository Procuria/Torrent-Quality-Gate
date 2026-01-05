FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY README.md .

ENV QG_DB_PATH=/data/qg.sqlite
ENV QG_MIN_RES_P=760
EXPOSE 8088

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]
