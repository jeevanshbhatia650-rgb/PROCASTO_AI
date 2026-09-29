# One service: the backend serves the built UI, the API and the WebSocket from a single origin.
# Untested here (no Docker on the dev machine); every step mirrors a command that was run locally.

FROM node:24-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.33 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    FASTEMBED_CACHE_PATH=/app/.fastembed \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --extra dense
COPY backend/app ./app
COPY backend/data ./data
# Bake the embedding model into the image: free hosts wipe the disk on every cold start.
RUN python -c "from app.retrieval.embedder import FastEmbedEmbedder; FastEmbedEmbedder()"
COPY --from=ui /ui/dist /app/frontend/dist
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --app-dir /app/backend --host 0.0.0.0 --port ${PORT}"]
