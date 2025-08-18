# Cloud-Hosted MCPD Architecture

## Overview
Run MCPD directly in the cloud as a managed service, providing MCP server capabilities without local installation.

## Simple Architecture

```
┌─────────────┐     ┌──────────────────────────────┐
│   Browser   │────▶│   Backend + MCPD (Railway)   │
└─────────────┘     │                              │
                    │  ┌────────────────────────┐  │
                    │  │   FastAPI Backend      │  │
                    │  │   - WebSocket handler  │  │
                    │  │   - Auth/Sessions      │  │
                    │  └──────────┬─────────────┘  │
                    │             │                │
                    │  ┌──────────▼─────────────┐  │
                    │  │   MCPD Process         │  │
                    │  │   - Running locally    │  │
                    │  │   - Port 8090          │  │
                    │  └──────────┬─────────────┘  │
                    │             │                │
                    │  ┌──────────▼─────────────┐  │
                    │  │   MCP Servers          │  │
                    │  │   - @github            │  │
                    │  │   - @sqlite            │  │
                    │  │   - Custom servers     │  │
                    │  └────────────────────────┘  │
                    └──────────────────────────────┘
```

## Implementation Strategy

### Option 1: Single Container (Simplest)
Run backend + MCPD in the same container.

```dockerfile
# Dockerfile
FROM golang:1.21 AS mcpd-builder
WORKDIR /build
COPY mcpd/ .
RUN go build -o mcpd ./cmd

FROM python:3.11-slim
WORKDIR /app

# Install Node.js for MCP servers
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy MCPD binary
COPY --from=mcpd-builder /build/mcpd /usr/local/bin/mcpd

# Install Python backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Install common MCP servers
RUN npm install -g \
    @modelcontextprotocol/server-github \
    @modelcontextprotocol/server-memory

# Copy backend code
COPY backend/ .

# Start script
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000
CMD ["./start.sh"]
```

```bash
#!/bin/bash
# start.sh

# Start MCPD in background
mcpd daemon --port 8090 &
MCPD_PID=$!

# Wait for MCPD to be ready
sleep 2

# Start Python backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Cleanup on exit
trap "kill $MCPD_PID" EXIT
```

### Option 2: Process Supervisor
Use supervisor to manage both processes properly.

```ini
# supervisord.conf
[supervisord]
nodaemon=true

[program:mcpd]
command=/usr/local/bin/mcpd daemon --port 8090
autostart=true
autorestart=true
stderr_logfile=/var/log/mcpd.err.log
stdout_logfile=/var/log/mcpd.out.log

[program:backend]
command=uvicorn app.main:app --host 0.0.0.0 --port 8000
directory=/app
autostart=true
autorestart=true
stderr_logfile=/var/log/backend.err.log
stdout_logfile=/var/log/backend.out.log
```

### Option 3: Docker Compose (Development/Small Scale)
```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - MCPD_BASE_URL=http://mcpd:8090/api/v1
    depends_on:
      - mcpd
    networks:
      - mcp-network

  mcpd:
    build: ./mcpd
    ports:
      - "8090:8090"
    volumes:
      - mcpd-data:/data
      - ./user-files:/workspace:ro  # Read-only user workspace
    networks:
      - mcp-network

networks:
  mcp-network:

volumes:
  mcpd-data:
```

## User Isolation Strategies

### 1. Namespace-Based Isolation (Linux)
```python
# backend/app/user_isolation.py
import os
import subprocess
from pathlib import Path
import tempfile

class UserMCPDManager:
    def __init__(self):
        self.user_workspaces = {}
        
    async def get_user_workspace(self, user_id: str):
        if user_id not in self.user_workspaces:
            # Create isolated workspace
            workspace = Path(f"/data/users/{user_id}")
            workspace.mkdir(parents=True, exist_ok=True)
            
            # Set up user-specific MCPD config
            config_path = workspace / ".mcpd.toml"
            config_path.write_text(f"""
                [mcpd]
                data_dir = "/data/users/{user_id}/mcpd"
                
                [servers.filesystem]
                root = "/data/users/{user_id}/files"
                readonly = false
                
                [servers.sqlite]
                db_path = "/data/users/{user_id}/database.db"
            """)
            
            self.user_workspaces[user_id] = workspace
            
        return self.user_workspaces[user_id]
    
    async def call_mcpd_for_user(self, user_id: str, endpoint: str, data: dict):
        workspace = await self.get_user_workspace(user_id)
        
        # Use separate MCPD instance per user (if needed)
        # Or use namespace/context switching
        headers = {
            "X-User-Context": user_id,
            "X-Workspace": str(workspace)
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8090{endpoint}",
                json=data,
                headers=headers
            )
            return response.json()
```

### 2. Multi-Tenant MCPD (Requires MCPD Modification)
```go
// mcpd modifications for multi-tenancy
type UserContext struct {
    UserID    string
    Workspace string
    Quota     ResourceQuota
}

func (s *Server) handleWithUserContext(w http.ResponseWriter, r *http.Request) {
    userID := r.Header.Get("X-User-ID")
    if userID == "" {
        http.Error(w, "User ID required", http.StatusUnauthorized)
        return
    }
    
    // Get or create user context
    ctx := s.getUserContext(userID)
    
    // Switch to user's workspace
    os.Chdir(ctx.Workspace)
    
    // Apply resource limits
    ctx.Quota.Apply()
    
    // Handle request in user context
    s.handleRequest(w, r, ctx)
}
```

### 3. Container-per-Request (Serverless Style)
```python
# backend/app/serverless_mcpd.py
import docker
import asyncio
import json

class ServerlessMCPD:
    def __init__(self):
        self.docker_client = docker.from_env()
        
    async def execute_mcp_request(
        self, 
        user_id: str,
        server: str,
        method: str,
        params: dict
    ):
        # Spin up ephemeral container
        container = self.docker_client.containers.run(
            "mcpd-runtime:latest",
            command=[
                "mcpd", "call",
                "--server", server,
                "--method", method,
                "--params", json.dumps(params)
            ],
            detach=True,
            remove=False,
            mem_limit="512m",
            cpu_quota=50000,  # 0.5 CPU
            volumes={
                f"/data/users/{user_id}": {
                    "bind": "/workspace",
                    "mode": "rw"
                }
            }
        )
        
        # Wait for completion (with timeout)
        try:
            result = container.wait(timeout=30)
            logs = container.logs().decode('utf-8')
            return json.loads(logs)
        finally:
            container.remove()
```

## Cloud Provider Options

### Railway (Recommended for Simplicity)
```toml
# railway.toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "./Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

[[services]]
name = "mcp-backend"
port = 8000

[[services]]
name = "mcpd"
port = 8090
internal = true  # Only accessible within project
```

### Google Cloud Run (Serverless)
```yaml
# service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: mcp-service
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/execution-environment: gen2
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containers:
      - image: gcr.io/PROJECT/mcp-service
        ports:
        - containerPort: 8000
        resources:
          limits:
            cpu: "2"
            memory: "2Gi"
        env:
        - name: MCPD_ENABLED
          value: "true"
```

### AWS ECS with Fargate
```json
{
  "family": "mcp-service",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/mcpTaskRole",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "mcp-backend",
      "image": "YOUR_ECR_URL/mcp-service:latest",
      "memory": 2048,
      "cpu": 1024,
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "MCPD_ENABLED",
          "value": "true"
        }
      ],
      "mountPoints": [
        {
          "sourceVolume": "user-data",
          "containerPath": "/data"
        }
      ]
    }
  ],
  "volumes": [
    {
      "name": "user-data",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-12345678"
      }
    }
  ]
}
```

## Limitations & Solutions

### Limitation 1: File System Access
**Problem**: Cloud MCPD can't access user's local files
**Solutions**:
- Upload files to cloud storage
- Use virtual filesystem backed by S3/GCS
- Provide web-based file editor

### Limitation 2: Git/SSH Operations
**Problem**: Can't use local git config or SSH keys
**Solutions**:
- OAuth-based git access (GitHub Apps)
- Store encrypted SSH keys in cloud
- Use git HTTP with tokens

### Limitation 3: Resource Costs
**Problem**: Running MCPD for each user is expensive
**Solutions**:
- Shared MCPD with strong isolation
- Scale to zero when inactive
- Usage-based billing

### Limitation 4: Network-Dependent Tools
**Problem**: Some MCP servers need external network access
**Solutions**:
- Proxy through backend
- Whitelist allowed domains
- Rate limiting

## Simplified Implementation Plan

### Phase 1: Basic Cloud MCPD
```python
# backend/app/main.py
import subprocess
import asyncio
from fastapi import FastAPI, WebSocket
import httpx

app = FastAPI()

# Start MCPD on startup
@app.on_event("startup")
async def startup_mcpd():
    # Start MCPD process
    subprocess.Popen([
        "mcpd", "daemon", 
        "--port", "8090",
        "--data-dir", "/data/mcpd"
    ])
    
    # Wait for MCPD to be ready
    await asyncio.sleep(2)
    
    # Install default servers
    async with httpx.AsyncClient() as client:
        await client.post("http://localhost:8090/api/v1/servers", json={
            "name": "@modelcontextprotocol/server-memory"
        })

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    
    # Bridge WebSocket to MCPD
    async with httpx.AsyncClient() as client:
        while True:
            data = await websocket.receive_json()
            
            # Forward to MCPD
            if data["type"] == "mcp_request":
                response = await client.post(
                    f"http://localhost:8090/api/v1/{data['endpoint']}",
                    json=data["payload"]
                )
                
                await websocket.send_json({
                    "type": "mcp_response",
                    "data": response.json()
                })
```

### Phase 2: Add User Isolation
- User-specific workspaces
- Resource quotas
- Activity logging

### Phase 3: Scale Optimizations
- Connection pooling
- Caching layer
- Background job processing

## Cost Analysis

| Provider | Setup | Monthly (10 users) | Monthly (100 users) |
|----------|-------|-------------------|---------------------|
| Railway | $5 | $20-30 | $100-200 |
| Cloud Run | $0 | $10-20 | $50-100 |
| AWS Fargate | $0 | $30-50 | $200-400 |
| Digital Ocean | $5 | $20-40 | $100-300 |

## Advantages

✅ **No installation required** - Just visit the website
✅ **Centralized updates** - Update MCPD once for all users  
✅ **Managed infrastructure** - No user maintenance
✅ **Collaborative potential** - Share workspaces/servers

## Disadvantages

❌ **Limited file access** - Can't access user's local files
❌ **Higher costs** - Running infrastructure 24/7
❌ **Network dependency** - Requires internet connection
❌ **Privacy concerns** - User data in cloud

## Recommendation

For a cloud MCPD, I recommend:

1. **Start with Railway** - Simple deployment, reasonable costs
2. **Single container with supervisor** - Both services in one container
3. **Virtual filesystem** - S3-backed storage per user
4. **OAuth for git** - Instead of SSH keys
5. **Usage-based limits** - Prevent abuse

This gives you MCP capabilities in the cloud without the complexity of my earlier proposals. The main trade-off is losing true local file system access, but you gain zero-installation convenience.