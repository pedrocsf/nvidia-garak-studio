FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefer-binary -r requirements.txt \
    && pip install --prefer-binary garak

COPY . .

EXPOSE 8000
CMD ["python", "run.py", "--no-reload"]
