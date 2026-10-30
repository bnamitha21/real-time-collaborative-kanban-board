FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final stage
FROM python:3.12-slim

WORKDIR /app

RUN useradd -m -u 1000 appuser && \
    apt-get update && apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY server/src /app/server/src
COPY server/migrations /app/server/migrations

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 4000

CMD ["sh", "-c", "python -m server.src.db.migrate && python -m server.src.main"]

