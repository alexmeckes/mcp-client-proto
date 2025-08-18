# Simple Python backend for MCP Client
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
WORKDIR /app

# Copy and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Create directories for user data
RUN mkdir -p /data/users

# Set environment variables for Railway
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV CLOUD_MODE=true

# Expose port (Railway will override PORT)
EXPOSE 8000

# Run the backend directly using PORT from environment
CMD sh -c "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"