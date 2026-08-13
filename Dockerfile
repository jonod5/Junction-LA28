# Base image — official Python, slim variant keeps it lightweight
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements first (Docker caches this layer — speeds up rebuilds)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your app code
COPY . .

# Railway injects PORT; default to 8000 for local dev.
# WEB_CONCURRENCY (Railway/Heroku-recognized name) sets worker process
# count — a load test found the previous single-worker default left every
# request on one CPU core with no multi-process fan-out. Each worker gets
# its own DB connection pool (see app/db.py's DB_POOL_SIZE/DB_MAX_OVERFLOW
# docstring) — raise both together, not just one.
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}