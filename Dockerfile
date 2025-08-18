# Multi-stage build for MCPD and backend
FROM golang:1.21-alpine AS mcpd-builder

# Install build dependencies
RUN apk add --no-cache git make

# Copy MCPD source
WORKDIR /build
COPY mcpd/ ./mcpd/

# Build MCPD
WORKDIR /build/mcpd
ENV GOPROXY=https://proxy.golang.org,direct
ENV GO111MODULE=on
RUN go mod download || (cat go.mod && exit 1)
RUN go build -o mcpd .

# Main application stage
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    nodejs \
    npm \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy MCPD binary from builder
COPY --from=mcpd-builder /build/mcpd/mcpd /usr/local/bin/mcpd
RUN chmod +x /usr/local/bin/mcpd

# Install some common MCP servers globally
RUN npm install -g \
    @modelcontextprotocol/server-memory

# Set up Python environment
WORKDIR /app

# Copy and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Create directories for MCPD data and logs
RUN mkdir -p /data/mcpd /var/log/supervisor /data/users

# Copy supervisor configuration
COPY backend/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create MCPD config
RUN echo '[mcpd]\n\
port = 8090\n\
data_dir = "/data/mcpd"\n\
log_level = "info"\n\
\n\
[cors]\n\
allowed_origins = ["*"]\n' > /data/mcpd/.mcpd.toml

# Set environment variables for Railway
ENV PORT=8000
ENV MCPD_ENABLED=true
ENV CLOUD_MODE=true
ENV PYTHONUNBUFFERED=1
ENV MCPD_BASE_URL=http://localhost:8090/api/v1
ENV MCPD_HEALTH_CHECK_URL=http://localhost:8090/health

# Expose ports (Railway will override PORT)
EXPOSE 8000 8090

# Use supervisor to manage both processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]