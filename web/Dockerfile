# Python 3.11+, pip, node for Tailwind build
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    libpq-dev \
    curl \
    nodejs \
    npm \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install pip deps
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Tailwind build (minimal, no hot reload)
COPY tailwind.config.js package.json ./
COPY static_src ./static_src
RUN mkdir -p static/css && npm install && npx tailwindcss -i ./static_src/input.css -o ./static/css/tailwind.css --minify || true

# Copy app
COPY . .

# Entrypoint
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8000
CMD ["/start.sh"]
