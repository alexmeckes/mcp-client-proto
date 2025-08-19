# Simple Railway deployment without building MCPD from source
# This uses a pre-built MCPD binary or runs without it

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    wget \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Download pre-built MCPD binary (if available)
# For now, we'll skip this and run without MCPD
# RUN wget https://github.com/your-org/mcpd/releases/download/v1.0.0/mcpd-linux-amd64 -O /usr/local/bin/mcpd && \
#     chmod +x /usr/local/bin/mcpd

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /data/mcpd /var/log/supervisor

# Set Railway environment variables
ENV PORT=8000
ENV MCPD_ENABLED=false
ENV PYTHONUNBUFFERED=1

# Expose port (Railway will override this)
EXPOSE 8000

# Run the backend directly (without MCPD for now)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]