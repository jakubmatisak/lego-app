# Jeden obraz: zostavený frontend aj backend, ktorý ho servuje.
# Databáza je jeden súbor SQLite na pripojenom zväzku.

FROM node:22-alpine AS frontend
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build-only


FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app/backend

# Závislosti zvlášť, aby sa vrstva neinvalidovala pri každej zmene kódu.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY backend/ ./
RUN uv sync --locked --no-dev

# Frontend musí byť vedľa backendu, main.py ho hľadá ako ../frontend/dist.
COPY --from=frontend /build/dist /app/frontend/dist

RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV DATABASE_URL=sqlite+aiosqlite:////app/data/lego.db
# Fotky musia ležať na zväzku vedľa databázy. Pracovný priečinok je
# /app/backend, relatívna cesta by ich uložila mimo zväzku a nasadenie
# novej verzie by ich zmazalo.
ENV PHOTOS_DIR=/app/data/photos

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).status == 200 else 1)"

# Migrácie beží aplikácia sama pri štarte (lifespan).
CMD ["uvicorn", "lego_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
