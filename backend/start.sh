#!/bin/bash
set -e

echo "Starting MCP Cloud Service..."

# Create necessary directories
mkdir -p /data/mcpd /data/users /var/log/supervisor

# Initialize MCPD configuration if it doesn't exist
if [ ! -f /data/mcpd/.mcpd.toml ]; then
    echo "Initializing MCPD configuration..."
    cat > /data/mcpd/.mcpd.toml << EOF
[mcpd]
port = 8090
data_dir = "/data/mcpd"
log_level = "info"

[cors]
allowed_origins = ["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"]

[servers]
# Pre-configured servers will be added here
EOF
fi

# Wait for MCPD to be healthy
wait_for_mcpd() {
    echo "Waiting for MCPD to start..."
    for i in {1..30}; do
        if curl -s http://localhost:8090/health > /dev/null 2>&1; then
            echo "MCPD is ready!"
            return 0
        fi
        sleep 1
    done
    echo "MCPD failed to start"
    return 1
}

# Start supervisor in background to launch MCPD
supervisord -c /etc/supervisor/conf.d/supervisord.conf &

# Wait for MCPD
wait_for_mcpd

# Install default MCP servers if not already installed
echo "Setting up default MCP servers..."
curl -X POST http://localhost:8090/api/v1/servers \
    -H "Content-Type: application/json" \
    -d '{"name": "@modelcontextprotocol/server-memory"}' || true

curl -X POST http://localhost:8090/api/v1/servers \
    -H "Content-Type: application/json" \
    -d '{"name": "@modelcontextprotocol/server-time"}' || true

echo "MCP Cloud Service is ready!"

# Keep supervisor in foreground
wait