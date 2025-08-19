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

# Add common Vercel URLs
# In production, set FRONTEND_URL environment variable instead
ALLOWED_ORIGINS.extend([
    "https://mcp-client-proto-frontend.vercel.app",
    "https://mcp-client-proto-alexmeckes.vercel.app",
    "https://mcp-client-proto.vercel.app"
])

# MCPD removed - using remote servers only
MCPD_ENABLED = False  # MCPD is no longer used
MCPD_BASE_URL = None  # Not needed anymore
MCPD_HEALTH_CHECK_URL = None  # Not needed anymore

# API Keys (users will provide their own)
REQUIRE_API_KEYS = os.getenv("REQUIRE_API_KEYS", "true").lower() == "true"

# WebSocket configuration
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))

# Server storage (in production, use Redis or a database)
USE_PERSISTENT_STORAGE = os.getenv("USE_PERSISTENT_STORAGE", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", None)