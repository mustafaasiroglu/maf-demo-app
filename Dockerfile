# Multi-stage build for Python backend + Next.js frontend

# Stage 1: Build Next.js frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Set API URL for production (same origin)
ENV NEXT_PUBLIC_API_URL=""

# Build static export
RUN npm run build

# Stage 2: Python backend with static files
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Copy built frontend static files
COPY --from=frontend-builder /app/frontend/out ./static

# Create startup script
RUN echo '#!/bin/bash\nuvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}' > /app/start.sh && chmod +x /app/start.sh

# Expose port
EXPOSE 8000

# Start the application
CMD ["/app/start.sh"]
