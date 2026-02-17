FROM python:3.11-slim

WORKDIR /app

# Runtime deps only (no cmake — backend doesn't need stable-retro)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached unless pyproject.toml changes)
COPY pyproject.toml .
RUN mkdir -p src/rawl && touch src/rawl/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf src/rawl

# Copy actual source and reinstall (fast — deps already cached)
COPY src/ src/
RUN pip install --no-cache-dir --no-deps .

COPY alembic.ini .
COPY alembic/ alembic/

EXPOSE 8080

CMD ["uvicorn", "rawl.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
