# Multi-stage build for MCPD and backend
FROM golang:1.21-alpine AS mcpd-builder

# Install build dependencies
RUN apk add --no-cache git make

# Copy MCPD source
WORKDIR /build
COPY ../mcpd /build/mcpd

# Build MCPD
WORKDIR /build/mcpd
RUN go mod download
RUN go build -o mcpd ./cmd

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
    @modelcontextprotocol/server-memory \
    @modelcontextprotocol/server-time

# Set up Python environment
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for MCPD data and logs
RUN mkdir -p /data/mcpd /var/log/supervisor

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose ports
EXPOSE 8000 8090

# Use supervisor to manage both processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]