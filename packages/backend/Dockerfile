FROM python:3.11-slim

WORKDIR /app

# Build deps for stable-retro (cmake), runtime deps for opencv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

COPY alembic.ini .
COPY alembic/ alembic/

EXPOSE 8080

CMD ["uvicorn", "rawl.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
