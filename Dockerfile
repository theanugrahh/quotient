# syntax=docker/dockerfile:1

FROM node:22-alpine AS web
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 quotient

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY --from=web /build/frontend/dist ./frontend/dist

RUN mkdir -p /app/data/uploads && chown -R quotient:quotient /app

USER quotient
WORKDIR /app/backend

ENV PYTHONPATH=/app/backend \
    DATABASE_URL=sqlite:////app/data/quotient.db \
    UPLOADS_DIR=/app/data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
