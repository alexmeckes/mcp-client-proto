"""
Production configuration for the MCP Client backend
"""
import os
from typing import List

# CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:5174").split(",")

# Add production frontend URL when deployed
if os.getenv("FRONTEND_URL"):
    ALLOWED_ORIGINS.append(os.getenv("FRONTEND_URL"))

# MCPD configuration - embedded in cloud deployment
MCPD_ENABLED = os.getenv("MCPD_ENABLED", "true").lower() == "true"  # Default to true in cloud
MCPD_BASE_URL = os.getenv("MCPD_BASE_URL", "http://localhost:8090/api/v1")
MCPD_HEALTH_CHECK_URL = os.getenv("MCPD_HEALTH_CHECK_URL", "http://localhost:8090/api/v1/health")

# API Keys (users will provide their own)
REQUIRE_API_KEYS = os.getenv("REQUIRE_API_KEYS", "true").lower() == "true"

# WebSocket configuration
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))

# Server storage (in production, use Redis or a database)
USE_PERSISTENT_STORAGE = os.getenv("USE_PERSISTENT_STORAGE", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", None)