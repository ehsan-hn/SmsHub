FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

COPY . .

FROM python:3.11-slim


WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

USER root

# Default command
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
