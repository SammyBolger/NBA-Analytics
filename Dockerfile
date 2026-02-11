# ---------- Stage 1: build frontend ----------
FROM node:22-alpine AS frontend
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: run backend ----------
FROM python:3.12-slim AS backend
WORKDIR /app

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY backend/ ./backend
COPY run_backend.py ./
COPY tests/ ./tests
COPY README.md ./

# Copy built frontend into the location backend/main.py expects: /app/frontend/dist
COPY --from=frontend /app/frontend/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1

# Render provides $PORT
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
