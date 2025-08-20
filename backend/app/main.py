from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import httpx
import json
import asyncio
# We'll use any-llm for all LLM calls instead of direct SDK
# from anthropic import AsyncAnthropic  # No longer needed
import os
from dotenv import load_dotenv
import tomli
import toml
from pathlib import Path
from any_llm import completion
import openai
import subprocess
# Removed tool_handler import since we'll simplify without Anthropic SDK
# from app.tool_handler import handle_tool_use_response
from app.composio_integration import ComposioIntegration
from fastapi.responses import RedirectResponse, JSONResponse
import uuid

load_dotenv()

app = FastAPI(title="MCP Test Client API - Multi-Model")

# Import config if it exists, otherwise use defaults
try:
    from app.config import ALLOWED_ORIGINS, MCPD_ENABLED, MCPD_BASE_URL, MCPD_HEALTH_CHECK_URL
except ImportError:
    ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]
    MCPD_ENABLED = os.getenv("MCPD_ENABLED", "true").lower() == "true"
    MCPD_BASE_URL = os.getenv("MCPD_BASE_URL", "http://localhost:8090/api/v1")
    MCPD_HEALTH_CHECK_URL = os.getenv("MCPD_HEALTH_CHECK_URL", "http://localhost:8090/api/v1/health")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins temporarily for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API keys - now optional, users can provide them via UI
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Store user-provided API keys (in production, use secure storage)
user_api_keys = {
    "anthropic": ANTHROPIC_API_KEY,
    "openai": OPENAI_API_KEY,
    "mistral": MISTRAL_API_KEY,
    "ollama_host": OLLAMA_HOST
}

# No longer need Anthropic client - using any-llm for everything

# Track MCPD status
mcpd_available = False


@app.on_event("startup")
async def startup_event():
    """Check if MCPD is available on startup"""
    global mcpd_available
    
    print("🚀 FastAPI startup event triggered")
    
    if not MCPD_ENABLED:
        print("MCPD is disabled in configuration")
        print("🚀 Startup complete - server should be ready!")
        return
    
    print(f"Checking MCPD availability at {MCPD_HEALTH_CHECK_URL}...")
    
    # Try to connect to MCPD with retries
    for attempt in range(10):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(MCPD_HEALTH_CHECK_URL)
                if response.status_code == 200:
                    mcpd_available = True
                    print(f"✓ MCPD is available at {MCPD_BASE_URL}")
                    
                    # Try to install default servers if in cloud mode
                    if os.getenv("CLOUD_MODE") == "true":
                        await setup_default_servers()
                    return
        except Exception as e:
            if attempt < 9:
                print(f"Attempt {attempt + 1}/10: Waiting for MCPD... ({str(e)})")
                await asyncio.sleep(2)
            else:
                print(f"✗ MCPD is not available: {str(e)}")
                print("MCP server features will be disabled")


async def setup_default_servers():
    """Install default MCP servers in cloud mode"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Install memory server
            try:
                response = await client.post(
                    f"{MCPD_BASE_URL}/servers",
                    json={"name": "@modelcontextprotocol/server-memory"}
                )
                if response.status_code in [200, 201]:
                    print("✓ Installed memory MCP server")
            except Exception as e:
                print(f"Could not install memory server: {e}")
            
            # Install time server
            try:
                response = await client.post(
                    f"{MCPD_BASE_URL}/servers",
                    json={"name": "@modelcontextprotocol/server-time"}
                )
                if response.status_code in [200, 201]:
                    print("✓ Installed time MCP server")
            except Exception as e:
                print(f"Could not install time server: {e}")
    except Exception as e:
        print(f"Error setting up default servers: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint for the backend"""
    try:
        return {
            "status": "healthy",
            "mcpd_available": mcpd_available,
            "mcpd_url": MCPD_BASE_URL if mcpd_available else None,
            "composio_available": composio is not None,
            "port": os.getenv("PORT"),
            "timestamp": "2025-08-19T20:00:00Z"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/debug")
async def debug_info():
    """Debug endpoint to check server status"""
    # Include remote MCP servers info for debugging
    remote_servers_info = {}
    for name, config in remote_mcp_servers.items():
        remote_servers_info[name] = {
            "endpoint": config.endpoint,
            "has_auth_token": bool(config.auth_token),
            "headers": {k: v for k, v in config.headers.items() if k != "Authorization"}
        }
    
    # Include MCP server mappings
    mappings_info = {}
    for key, value in mcp_server_mappings.items():
        mappings_info[key] = value
    
    return {
        "message": "Server is running!",
        "composio_status": "available" if composio else "unavailable",
        "environment": {
            "PORT": os.getenv("PORT"),
            "COMPOSIO_API_KEY": "SET" if os.getenv("COMPOSIO_API_KEY") else "NOT SET",
            "MCPD_ENABLED": MCPD_ENABLED
        },
        "remote_mcp_servers": remote_servers_info,
        "mcp_server_mappings": mappings_info
    }

# Add startup debugging
print("🚀 Starting MCP Client API...")
print(f"🚀 Python path: {os.path.abspath('.')}")
print(f"🚀 Environment variables: PORT={os.getenv('PORT')}, COMPOSIO_API_KEY={'SET' if os.getenv('COMPOSIO_API_KEY') else 'NOT SET'}")

# Initialize Composio integration with error handling
try:
    print("🚀 Initializing Composio integration...")
    composio = ComposioIntegration()
    print("✅ Composio integration initialized successfully")
except Exception as e:
    print(f"⚠️ Failed to initialize Composio integration: {e}")
    print("Continuing without Composio integration...")
    composio = None

print("🚀 FastAPI app initialization complete")

class ComposioConnectRequest(BaseModel):
    user_id: str
    app_name: str
    callback_url: Optional[str] = None

@app.post("/composio/connect")
async def composio_connect(request: ComposioConnectRequest):
    """Initiate Composio connection for a specific app"""
    print(f"Composio connect request: user={request.user_id}, app={request.app_name}")
    
    if not composio or not composio.is_configured():
        print("Composio not configured or not available")
        return {
            "error": "Composio integration not available. Please check COMPOSIO_API_KEY."
        }
    
    print(f"Initiating OAuth connection for {request.app_name}")
    # Initiate OAuth connection through Composio
    result = await composio.initiate_connection(
        user_id=request.user_id,
        app_name=request.app_name,
        callback_url=request.callback_url
    )
    
    if "error" in result:
        print(f"Error initiating connection: {result['error']}")
        return JSONResponse(status_code=400, content=result)
    
    print(f"Connection initiated successfully: {result.get('redirect_url', 'No URL')}")
    return {
        "mode": "oauth",
        **result
    }

@app.get("/composio/connections/{user_id}")
async def get_composio_connections(user_id: str):
    """Get user's connected Composio apps"""
    if not composio:
        return {"connections": []}
    connections = await composio.get_user_connections(user_id)
    return {"connections": connections}

@app.get("/composio/tools/{user_id}")
async def get_composio_tools(user_id: str, app_name: Optional[str] = None):
    """Get available tools for user's connected apps"""
    tools = await composio.get_available_tools(user_id, app_name)
    return {"tools": tools}

# Removed unused gmail-tools-direct endpoint

class AddMCPServerRequest(BaseModel):
    user_id: str
    app_name: str

@app.post("/composio/disconnect")
async def disconnect_composio(request: AddMCPServerRequest):
    """Disconnect a Composio app for a user"""
    print(f"Disconnecting {request.app_name} for user {request.user_id}")
    
    try:
        # Remove from MCP server mappings
        mapping_key = f"{request.user_id}:{request.app_name}"
        if mapping_key in mcp_server_mappings:
            del mcp_server_mappings[mapping_key]
            print(f"Removed MCP server mapping for {mapping_key}")
        
        # Remove from remote servers
        server_name = f"composio-{request.app_name}"
        if server_name in remote_mcp_servers:
            del remote_mcp_servers[server_name]
            print(f"Removed remote server {server_name}")
        
        # Disconnect via Composio API
        success = await composio.disconnect_app(request.user_id, request.app_name)
        
        return {
            "success": success,
            "message": f"Disconnected {request.app_name}" if success else "Disconnect failed"
        }
    except Exception as e:
        print(f"Error disconnecting: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/composio/test-auth-config/{app_name}")
async def test_auth_config(app_name: str):
    """Test if we can get/create auth config for an app"""
    print(f"🧪 Testing auth config for {app_name}")
    
    try:
        auth_config_id = await composio.get_or_create_auth_config(app_name)
        print(f"🧪 Result: {auth_config_id}")
        
        return {
            "success": bool(auth_config_id and auth_config_id.startswith("ac_")),
            "auth_config_id": auth_config_id,
            "valid": auth_config_id.startswith("ac_") if auth_config_id else False
        }
    except Exception as e:
        print(f"🧪 Error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/composio/fix-auth-config")
async def fix_auth_config(request: AddMCPServerRequest):
    """Ensure we have a proper auth_config_id for an app"""
    print(f"Fixing auth config for {request.app_name}")
    
    # Get or create proper auth config
    if not composio:
        return {"error": "Composio integration not available", "added": False}
    
    auth_config_id = await composio.get_or_create_auth_config(request.app_name)
    
    if auth_config_id and auth_config_id.startswith("ac_"):
        print(f"Got proper auth_config_id: {auth_config_id}")
        return {
            "success": True,
            "auth_config_id": auth_config_id,
            "message": f"Auth config ready for {request.app_name}"
        }
    else:
        print(f"Failed to get proper auth config for {request.app_name}")
        return {
            "success": False,
            "message": "Could not get or create auth config"
        }

@app.post("/composio/add-mcp-server")
async def add_composio_mcp_server(request: AddMCPServerRequest):
    """Add a Composio app as an MCP server by creating a server instance"""
    print(f"Adding MCP server for {request.app_name} for user {request.user_id}")
    
    server_name = f"composio-{request.app_name}"
    mapping_key = f"{request.user_id}:{request.app_name}"
    
    # Check if we already have a server for this user/app combination
    if mapping_key in mcp_server_mappings:
        server_uuid = mcp_server_mappings[mapping_key]
        # Use the proper MCP URL format with /mcp path and user_id parameter
        mcp_url = f"https://mcp.composio.dev/composio/server/{server_uuid}/mcp?user_id={request.user_id}"
        print(f"Using existing MCP server {server_uuid} for {request.app_name}")
        
        # DON'T recreate/update the server - just use the existing one!
        # This was causing working servers to be replaced with broken ones
        print(f"✅ Keeping existing server (not recreating) to preserve working configuration")
    else:
        # Create a new MCP server instance via Composio API
        server_result = await composio.create_mcp_server(request.user_id, request.app_name)
        
        if not server_result:
            # Fallback to old method if server creation fails
            print(f"Failed to create MCP server via API, using fallback URL")
            mcp_url = composio.get_mcp_url_for_app(request.user_id, request.app_name)
        else:
            server_uuid = server_result["server_id"]
            mcp_url = server_result["url"]
            
            # CRITICAL FIX: Ensure the URL has /mcp path and user_id parameter
            if not mcp_url.endswith("/mcp") and "/mcp?" not in mcp_url:
                # URL is missing the /mcp path, add it
                if not mcp_url.endswith("/"):
                    mcp_url += "/"
                mcp_url += "mcp"
            
            # Ensure user_id parameter is present
            if "user_id=" not in mcp_url:
                separator = "&" if "?" in mcp_url else "?"
                mcp_url = f"{mcp_url}{separator}user_id={request.user_id}"
            
            # Store the mapping
            mcp_server_mappings[mapping_key] = server_uuid
            print(f"Created new MCP server {server_uuid} for {request.app_name}")
            print(f"Fixed MCP URL: {mcp_url}")
    
    # Add to remote MCP servers
    remote_mcp_servers[server_name] = RemoteServerConfig(
        name=server_name,
        endpoint=mcp_url,
        auth_token=None,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Added MCP server {server_name} with URL {mcp_url}")
    
    return {
        "server_id": server_name,
        "url": mcp_url,
        "added": True
    }

@app.post("/fix-slack-mcp")
async def fix_slack_mcp(request: AddMCPServerRequest):
    """Force recreate Slack MCP server with correct user_id"""
    try:
        server_name = "composio-slack"
        mapping_key = f"{request.user_id}:slack"
        
        # Remove old server if exists
        if server_name in remote_mcp_servers:
            del remote_mcp_servers[server_name]
            print(f"Removed old Slack server")
        
        # Remove old mapping if exists
        if mapping_key in mcp_server_mappings:
            del mcp_server_mappings[mapping_key]
            print(f"Removed old Slack mapping")
        
        # Create new server via Composio
        server_result = await composio.create_mcp_server(request.user_id, "slack")
        
        if server_result:
            server_uuid = server_result["server_id"]
            # Ensure user_id is in the URL
            mcp_url = server_result["url"]
            if "user_id=" not in mcp_url:
                # Add user_id if missing
                separator = "&" if "?" in mcp_url else "?"
                mcp_url = f"{mcp_url}{separator}user_id={request.user_id}"
            
            # Store the mapping
            mcp_server_mappings[mapping_key] = server_uuid
            
            # Add to remote MCP servers with correct URL
            remote_mcp_servers[server_name] = RemoteServerConfig(
                name=server_name,
                endpoint=mcp_url,
                auth_token=None,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"Fixed Slack MCP server with URL: {mcp_url}")
            
            return {
                "success": True,
                "server_id": server_uuid,
                "url": mcp_url,
                "message": f"Slack MCP server recreated with user_id: {request.user_id}"
            }
        else:
            return {"success": False, "message": "Failed to create MCP server"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/refresh-mcpd")
async def refresh_mcpd():
    """Refresh MCPD availability status"""
    global mcpd_available
    
    if not MCPD_ENABLED:
        return {"status": "disabled", "message": "MCPD is disabled"}
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try the correct MCPD health endpoint
            response = await client.get("http://localhost:8090/api/v1/health")
            if response.status_code == 200:
                mcpd_available = True
                return {"status": "success", "message": "MCPD is now available", "mcpd_available": True}
    except Exception as e:
        pass
    
    return {"status": "not_available", "message": "MCPD is not responding", "mcpd_available": False}

@app.get("/debug/mcpd")
async def debug_mcpd():
    """Debug endpoint to check MCPD status"""
    import shutil
    import subprocess
    
    mcpd_path = "/usr/local/bin/mcpd" if os.getenv("CLOUD_MODE") == "true" else "mcpd"
    
    # Try to refresh MCPD status
    global mcpd_available
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(MCPD_HEALTH_CHECK_URL)
            if response.status_code == 200:
                mcpd_available = True
    except:
        pass
    
    debug_info = {
        "cloud_mode": os.getenv("CLOUD_MODE"),
        "mcpd_enabled": os.getenv("MCPD_ENABLED"),
        "mcpd_path": mcpd_path,
        "mcpd_exists": os.path.exists(mcpd_path) if "/" in mcpd_path else shutil.which(mcpd_path) is not None,
        "mcpd_executable": os.access(mcpd_path, os.X_OK) if os.path.exists(mcpd_path) else False,
        "mcpd_base_url": MCPD_BASE_URL,
        "mcpd_available": mcpd_available
    }
    
    # Try to check if mcpd is running
    try:
        result = subprocess.run(["pgrep", "-f", "mcpd"], capture_output=True, text=True)
        debug_info["mcpd_processes"] = result.stdout.strip().split('\n') if result.stdout.strip() else []
    except:
        debug_info["mcpd_processes"] = []
    
    # Check supervisor status if available
    try:
        result = subprocess.run(["supervisorctl", "status"], capture_output=True, text=True)
        debug_info["supervisor_status"] = result.stdout
    except:
        debug_info["supervisor_status"] = "supervisorctl not available"
    
    return debug_info


class ChatMessage(BaseModel):
    role: str
    content: str


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    requires_key: bool
    is_available: bool = False
    supports_tools: bool = False


class ModelsResponse(BaseModel):
    models: List[ModelInfo]


class UpdateKeysRequest(BaseModel):
    keys: Dict[str, str]


@app.get("/models")
def get_available_models() -> ModelsResponse:
    """Get list of available models with their status"""
    models = [
        # Claude 4 models (Latest generation)
        ModelInfo(
            id="anthropic/claude-opus-4-1-20250805",
            name="Claude Opus 4.1 (Latest)",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True  # Supported via any-llm
        ),
        ModelInfo(
            id="anthropic/claude-opus-4-20250514",
            name="Claude Opus 4",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True  # Supported via any-llm
        ),
        ModelInfo(
            id="anthropic/claude-sonnet-4-20250514",
            name="Claude Sonnet 4",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True  # Supported via any-llm
        ),
        # Claude 3.7
        ModelInfo(
            id="anthropic/claude-3-7-sonnet-20250219",
            name="Claude Sonnet 3.7",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True  # Supported via any-llm
        ),
        # Claude 3.5 models
        ModelInfo(
            id="anthropic/claude-3-5-sonnet-20241022",
            name="Claude 3.5 Sonnet v2",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True  # Supported via any-llm
        ),
        ModelInfo(
            id="anthropic/claude-3-5-sonnet-20240620",
            name="Claude 3.5 Sonnet",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True  # Supported via any-llm
        ),
        ModelInfo(
            id="anthropic/claude-3-5-haiku-20241022",
            name="Claude 3.5 Haiku",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True  # Supported via any-llm
        ),
        # Claude 3 models
        ModelInfo(
            id="anthropic/claude-3-haiku-20240307",
            name="Claude 3 Haiku",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True  # Supported via any-llm
        ),
        # OpenAI GPT-5 models (Latest generation - August 2025)
        ModelInfo(
            id="openai/gpt-5",
            name="GPT-5 (Latest)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-5-mini",
            name="GPT-5 Mini",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-5-nano",
            name="GPT-5 Nano",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-5-chat",
            name="GPT-5 Chat",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        # OpenAI GPT-4.5
        ModelInfo(
            id="openai/gpt-4.5",
            name="GPT-4.5",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        # OpenAI o1 models (Reasoning models)
        ModelInfo(
            id="openai/o1",
            name="o1 (Advanced Reasoning)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/o1-mini",
            name="o1-mini (Fast Reasoning)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/o1-preview",
            name="o1-preview",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        # OpenAI GPT-4o models
        ModelInfo(
            id="openai/gpt-4o",
            name="GPT-4o (Latest)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False  # For simplicity, not implementing OpenAI tools yet
        ),
        ModelInfo(
            id="openai/gpt-4o-2024-11-20",
            name="GPT-4o (Nov 2024)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4o-2024-08-06",
            name="GPT-4o (Aug 2024)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4o-2024-05-13",
            name="GPT-4o (May 2024)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4o-mini",
            name="GPT-4o-mini (Latest)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4o-mini-2024-07-18",
            name="GPT-4o-mini (July 2024)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        # OpenAI GPT-4 Turbo models
        ModelInfo(
            id="openai/gpt-4-turbo",
            name="GPT-4 Turbo (Latest)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4-turbo-2024-04-09",
            name="GPT-4 Turbo (April 2024)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4-turbo-preview",
            name="GPT-4 Turbo Preview",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4-0125-preview",
            name="GPT-4 Turbo (Jan 2024)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4-1106-preview",
            name="GPT-4 Turbo (Nov 2023)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        # OpenAI GPT-4 models
        ModelInfo(
            id="openai/gpt-4",
            name="GPT-4",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4-0613",
            name="GPT-4 (June 2023)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4-32k",
            name="GPT-4 32K",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-4-32k-0613",
            name="GPT-4 32K (June 2023)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        # OpenAI GPT-3.5 models
        ModelInfo(
            id="openai/gpt-3.5-turbo",
            name="GPT-3.5 Turbo (Latest)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-3.5-turbo-0125",
            name="GPT-3.5 Turbo (Jan 2024)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-3.5-turbo-1106",
            name="GPT-3.5 Turbo (Nov 2023)",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="openai/gpt-3.5-turbo-16k",
            name="GPT-3.5 Turbo 16K",
            provider="openai",
            requires_key=True,
            is_available=bool(user_api_keys.get("openai")),
            supports_tools=False
        ),
        ModelInfo(
            id="mistral/mistral-medium-latest",
            name="Mistral Medium",
            provider="mistral",
            requires_key=True,
            is_available=bool(user_api_keys.get("mistral")),
            supports_tools=False
        ),
        ModelInfo(
            id="mistral/mistral-small-latest",
            name="Mistral Small",
            provider="mistral",
            requires_key=True,
            is_available=bool(user_api_keys.get("mistral")),
            supports_tools=False
        ),
        ModelInfo(
            id="ollama/llama2",
            name="Llama 2 (Local)",
            provider="ollama",
            requires_key=False,
            is_available=True,  # Assume local is available
            supports_tools=False
        ),
        ModelInfo(
            id="ollama/mistral",
            name="Mistral (Local)",
            provider="ollama",
            requires_key=False,
            is_available=True,
            supports_tools=False
        ),
    ]
    return ModelsResponse(models=models)


@app.post("/update-keys")
def update_api_keys(request: UpdateKeysRequest):
    """Update API keys for model providers"""
    global user_api_keys
    
    user_api_keys.update(request.keys)
    
    # Update environment variables for any-llm
    if "anthropic" in request.keys and request.keys["anthropic"]:
        os.environ["ANTHROPIC_API_KEY"] = request.keys["anthropic"]
    if "openai" in request.keys and request.keys["openai"]:
        os.environ["OPENAI_API_KEY"] = request.keys["openai"]
    if "mistral" in request.keys and request.keys["mistral"]:
        os.environ["MISTRAL_API_KEY"] = request.keys["mistral"]
    if "ollama_host" in request.keys and request.keys["ollama_host"]:
        os.environ["OLLAMA_HOST"] = request.keys["ollama_host"]
    
    return {"status": "success"}


@app.get("/servers")
async def list_servers():
    """List available MCP servers from both mcpd and remote sources"""
    servers = []
    
    # Get local servers from mcpd (only if available and configured)
    if MCPD_ENABLED and MCPD_BASE_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                print(f"Trying to fetch servers from: {MCPD_BASE_URL}/servers")
                response = await client.get(f"{MCPD_BASE_URL}/servers")
                response.raise_for_status()
                local_servers = response.json()
                print(f"Got servers from MCPD: {local_servers}")
                # Mark these as local servers
                servers.extend([{"name": s, "type": "local"} for s in local_servers])
        except httpx.HTTPError as e:
            print(f"Failed to fetch servers from MCPD: {e}")
            pass  # mcpd might not be running
        except Exception as e:
            print(f"Unexpected error fetching servers: {e}")
    
    # Add remote servers
    for name, config in remote_mcp_servers.items():
        servers.append({
            "name": name,
            "type": "remote",
            "endpoint": config.endpoint
        })
    
    return servers


@app.get("/servers/{server_name}/auth-status")
async def get_server_auth_status(server_name: str):
    """Check authentication status for a server (stub for now)"""
    # For Composio servers, we could check if the customerId is valid
    # For now, just return authenticated for remote servers
    if server_name in remote_mcp_servers:
        config = remote_mcp_servers[server_name]
        # Composio servers with customerId are considered authenticated
        if "composio" in config.endpoint and "customerId=" in config.endpoint:
            return {"authenticated": True, "type": "composio"}
        # Other remote servers with tokens are authenticated
        elif config.auth_token:
            return {"authenticated": True, "type": "token"}
        else:
            return {"authenticated": False, "message": "No authentication configured"}
    
    # Local servers don't need authentication
    return {"authenticated": True, "type": "local"}

@app.get("/servers/{server_name}/tools")
async def get_server_tools(server_name: str):
    """Get tools for a specific MCP server (local or remote)"""
    # Check if it's a remote server
    if server_name in remote_mcp_servers:
        config = remote_mcp_servers[server_name]
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                headers = config.headers.copy()
                
                # Check if it's Composio (they use SSE)
                is_composio = "composio" in config.endpoint
                if is_composio:
                    headers["Accept"] = "application/json, text/event-stream"
                    # Composio expects customerId in URL, not auth header
                elif config.auth_token:
                    headers["Authorization"] = f"Bearer {config.auth_token}"
                
                # Initialize MCP session first
                init_response = await client.post(
                    config.endpoint,
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "0.1.0",
                            "capabilities": {},
                            "clientInfo": {
                                "name": "mcp-client-proto",
                                "version": "1.0.0"
                            }
                        },
                        "id": 1
                    }
                )
                
                # Call remote server's tool listing endpoint
                response = await client.post(
                    config.endpoint,
                    headers=headers,
                    json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2}
                )
                response.raise_for_status()
                
                # Handle Composio's SSE response
                if is_composio and response.headers.get("content-type", "").startswith("text/event-stream"):
                    # Parse SSE response
                    text = response.text
                    result = None
                    for line in text.split('\n'):
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            try:
                                result = json.loads(data)
                                break
                            except:
                                continue
                    if not result:
                        result = {"error": "Failed to parse SSE response"}
                else:
                    result = response.json()
                
                # Extract tools from JSON-RPC response
                if "result" in result:
                    return {"tools": result["result"].get("tools", [])}
                return {"tools": []}
            except httpx.HTTPError as e:
                print(f"Error fetching tools from {server_name}: {e}")
                print(f"Endpoint: {config.endpoint}")
                print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
                if 'response' in locals():
                    print(f"Response text: {response.text[:500]}")
                raise HTTPException(status_code=503, detail=f"Failed to get tools from remote server: {str(e)}")
    
    # Otherwise, it's a local server via mcpd
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MCPD_BASE_URL}/servers/{server_name}/tools")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail=f"Failed to get tools: {str(e)}")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with selected model"""
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_json()
            messages = data.get("messages", [])
            available_servers = data.get("available_servers", [])
            model = data.get("model", "anthropic/claude-3-sonnet-20240229")
            api_keys = data.get("api_keys", {})
            
            # Debug logging
            print(f"Chat request - Model: {model}, Servers: {available_servers}")
            
            # Update API keys if provided
            if api_keys:
                for key, value in api_keys.items():
                    if value:
                        user_api_keys[key] = value
                        if key == "anthropic":
                            os.environ["ANTHROPIC_API_KEY"] = value
                        elif key == "openai":
                            os.environ["OPENAI_API_KEY"] = value
                        elif key == "mistral":
                            os.environ["MISTRAL_API_KEY"] = value
                        elif key == "ollama_host":
                            os.environ["OLLAMA_HOST"] = value
            
            # Check if model requires API key
            provider = model.split("/")[0]
            if provider in ["anthropic", "openai", "mistral"] and not user_api_keys.get(provider):
                await websocket.send_json({
                    "type": "error",
                    "message": f"{provider.capitalize()} API key required for {model}"
                })
                continue
            
            # Gather tools if available and model supports them
            tools = []
            # Check if model supports tools (Anthropic, OpenAI GPT-4, etc.)
            supports_tools = (
                model.startswith("anthropic/") or 
                model.startswith("openai/gpt-4") or
                model.startswith("openai/gpt-3.5-turbo")
            )
            print(f"Model: {model}, Supports tools: {supports_tools}, Available servers: {available_servers}")
            if available_servers and supports_tools:
                for server in available_servers:
                    try:
                        # Check if it's a remote server or local
                        if server in remote_mcp_servers:
                            # Fetch tools from remote server
                            config = remote_mcp_servers[server]
                            print(f"Fetching tools from remote server {server} at {config.endpoint}")
                            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                                headers = config.headers.copy()
                                is_composio = "composio" in config.endpoint
                                if is_composio:
                                    headers["Accept"] = "application/json, text/event-stream"
                                    # Composio uses the customerId in the URL for auth
                                elif config.auth_token:
                                    headers["Authorization"] = f"Bearer {config.auth_token}"
                                
                                # For Composio, try a simple GET first to see what's available
                                if is_composio:
                                    try:
                                        get_response = await client.get(config.endpoint, headers=headers)
                                        print(f"GET response status from {server}: {get_response.status_code}")
                                        print(f"GET response headers: {dict(get_response.headers)}")
                                        if get_response.status_code == 200:
                                            print(f"GET response from {server}: {get_response.text[:500]}")
                                    except Exception as e:
                                        print(f"GET request failed: {str(e)}")
                                
                                print(f"🔧 Continuing after GET request to initialize MCP session for {server}")
                                
                                # Initialize server_tools and session tracking
                                server_tools = []
                                mcp_session_id = None
                                negotiated_protocol = "2025-03-26"
                                
                                print(f"🔧 About to send initialize request to {config.endpoint}")
                                # First, initialize the MCP session
                                # Use the newer protocol version that Composio supports
                                init_headers = headers.copy()
                                init_headers["Accept"] = "application/json, text/event-stream"
                                
                                init_response = await client.post(
                                    config.endpoint,
                                    headers=init_headers,
                                    json={
                                        "jsonrpc": "2.0", 
                                        "method": "initialize", 
                                        "params": {
                                            "protocolVersion": "2025-03-26",  # Updated to match Composio's version
                                            "capabilities": {
                                                "tools": {},  # Indicate we support tools
                                                "resources": {}  # Indicate we support resources
                                            },
                                            "clientInfo": {
                                                "name": "mcp-client-proto",
                                                "version": "1.0.0"
                                            }
                                        }, 
                                        "id": 1
                                    }
                                )
                                
                                # Check for MCP session header (debug all headers)
                                print(f"🔧 Init response headers: {dict(init_response.headers)}")
                                session_id_found = False
                                for header_name in ["mcp-session-id", "Mcp-Session-Id", "x-mcp-session-id", "X-MCP-Session-Id"]:
                                    if header_name in init_response.headers:
                                        mcp_session_id = init_response.headers[header_name]
                                        print(f"Got MCP session ID ({header_name}): {mcp_session_id}")
                                        session_id_found = True
                                        
                                        # Store session ID in server config for later tool execution
                                        if server in remote_mcp_servers:
                                            remote_mcp_servers[server].headers["Mcp-Session-Id"] = mcp_session_id
                                            print(f"Stored MCP session ID for {server}: {mcp_session_id}")
                                        break
                                
                                if not session_id_found:
                                    print(f"🔧 No session ID found in headers for {server} - authentication may be URL-based")
                                
                                if init_response.status_code == 200:
                                    print(f"MCP session initialized for {server}")
                                    
                                    # Send initialized notification as required by MCP spec
                                    initialized_response = await client.post(
                                        config.endpoint,
                                        headers=init_headers,
                                        json={
                                            "jsonrpc": "2.0",
                                            "method": "notifications/initialized",
                                            "params": {}
                                        }
                                    )
                                    print(f"Sent initialized notification, status: {initialized_response.status_code}")
                                    
                                    # Check content type
                                    content_type = init_response.headers.get("content-type", "")
                                    print(f"Init response content-type: {content_type}")
                                    
                                    # Parse response based on content type
                                    try:
                                        if "text/event-stream" in content_type:
                                            # Parse SSE response
                                            print("Parsing SSE init response...")
                                            text = init_response.text
                                            for line in text.split('\n'):
                                                if line.startswith('data: '):
                                                    data = line[6:]
                                                    try:
                                                        init_result = json.loads(data)
                                                        print(f"Initialize SSE response: {json.dumps(init_result, indent=2)[:500]}")
                                                        
                                                        # Check for tools in result.tools
                                                        if "result" in init_result:
                                                            # Log the ENTIRE init result to see what we're getting
                                                            print(f"FULL INIT RESULT: {json.dumps(init_result, indent=2)}")
                                                            
                                                            # Store the negotiated protocol version
                                                            if "protocolVersion" in init_result["result"]:
                                                                negotiated_protocol = init_result["result"]["protocolVersion"]
                                                                print(f"Negotiated protocol version: {negotiated_protocol}")
                                                                
                                                                # Store protocol version in server config for tool execution
                                                                if server in remote_mcp_servers:
                                                                    remote_mcp_servers[server].headers["Mcp-Protocol-Version"] = negotiated_protocol
                                                                    print(f"Stored protocol version for {server}: {negotiated_protocol}")
                                                            
                                                            # Check various possible locations for tools
                                                            if "tools" in init_result["result"] and isinstance(init_result["result"]["tools"], list):
                                                                print(f"Tools found as array in result.tools!")
                                                                server_tools = init_result["result"]["tools"]
                                                                print(f"Found {len(server_tools)} tools from initialize")
                                                                break
                                                            elif "serverInfo" in init_result["result"] and "tools" in init_result["result"]["serverInfo"]:
                                                                print(f"Tools found in serverInfo.tools!")
                                                                server_tools = init_result["result"]["serverInfo"]["tools"]
                                                                print(f"Found {len(server_tools)} tools from serverInfo")
                                                                break
                                                            # Also check if tools is empty dict (meaning we need to call tools/list)
                                                            elif "capabilities" in init_result["result"] and "tools" in init_result["result"]["capabilities"]:
                                                                print(f"Server has tools capability but no tools in init response")
                                                                # Check if capabilities.tools contains the actual tools
                                                                cap_tools = init_result["result"]["capabilities"]["tools"]
                                                                if isinstance(cap_tools, dict) and len(cap_tools) > 0:
                                                                    print(f"Found tools in capabilities: {list(cap_tools.keys())[:5]}")
                                                                # Will need to call tools/list
                                                    except:
                                                        continue
                                        else:
                                            # Regular JSON response
                                            init_result = init_response.json()
                                            print(f"Initialize JSON response: {json.dumps(init_result, indent=2)[:500]}")
                                            
                                            # Check for tools in result.tools
                                            if "result" in init_result:
                                                # Store the negotiated protocol version
                                                if "protocolVersion" in init_result["result"]:
                                                    negotiated_protocol = init_result["result"]["protocolVersion"]
                                                    print(f"Negotiated protocol version: {negotiated_protocol}")
                                                    
                                                    # Store protocol version in server config for tool execution
                                                    if server in remote_mcp_servers:
                                                        remote_mcp_servers[server].headers["Mcp-Protocol-Version"] = negotiated_protocol
                                                        print(f"Stored protocol version for {server}: {negotiated_protocol}")
                                                
                                                if "tools" in init_result["result"] and isinstance(init_result["result"]["tools"], list):
                                                    print(f"Tools found as array in initialize response!")
                                                    server_tools = init_result["result"]["tools"]
                                                    print(f"Found {len(server_tools)} tools from initialize")
                                                # Also check if tools is empty dict (meaning we need to call tools/list)
                                                elif "capabilities" in init_result["result"] and "tools" in init_result["result"]["capabilities"]:
                                                    print(f"Server has tools capability but no tools in init response")
                                    except Exception as e:
                                        print(f"Error parsing init response: {e}")
                                        print(f"Raw response: {init_response.text[:500]}")
                                    
                                    # Skip tools/list if we already have tools
                                    if server_tools and len(server_tools) > 0:
                                        print(f"Already have {len(server_tools)} tools from initialization, skipping tools/list")
                                        # Format them properly for our system
                                        for tool in server_tools:
                                            tools.append({
                                                "name": tool.get("name", ""),
                                                "description": tool.get("description", ""),
                                                "input_schema": tool.get("inputSchema", tool.get("input_schema", {})),
                                                "server": server
                                            })
                                        continue
                                    else:
                                        print(f"🔧 No tools found in init response, will call tools/list. server_tools={server_tools}")
                                
                                try:
                                    print(f"🔧 Starting tools/list section for {server}")
                                    # Prepare headers for tools/list request
                                    tools_headers = headers.copy()
                                    tools_headers["Accept"] = "application/json, text/event-stream"
                                    
                                    # Add MCP session headers if we have them
                                    if mcp_session_id:
                                        tools_headers["Mcp-Session-Id"] = mcp_session_id
                                        print(f"Including MCP session ID in tools request: {mcp_session_id}")
                                    
                                    # Add protocol version header
                                    tools_headers["Mcp-Protocol-Version"] = negotiated_protocol
                                    
                                    # Try different method names for Composio
                                    # First try the standard MCP method
                                    # According to MCP spec, tools/list doesn't need params
                                    tools_request = {
                                        "jsonrpc": "2.0", 
                                        "method": "tools/list", 
                                        "id": 2
                                    }
                                    print(f"Sending tools/list request: {json.dumps(tools_request)}")
                                    print(f"Endpoint: {config.endpoint}")
                                    print(f"Headers: {tools_headers}")
                                    
                                    # Add timeout to prevent hanging
                                    try:
                                        tool_response = await asyncio.wait_for(
                                            client.post(
                                                config.endpoint,
                                                headers=tools_headers,
                                                json=tools_request
                                            ),
                                            timeout=15.0  # 15 second timeout
                                        )
                                        print(f"🔧 tools/list response received")
                                    except asyncio.TimeoutError:
                                        print(f"🔧 ERROR: tools/list request timed out after 15 seconds!")
                                        server_tools = []
                                        continue
                                    except Exception as e:
                                        print(f"🔧 ERROR sending tools/list: {type(e).__name__}: {str(e)}")
                                        server_tools = []
                                        continue
                                    
                                    # If tools/list fails, try Composio-specific methods
                                    if tool_response.status_code == 200:
                                        try:
                                            test_json = tool_response.json() if "application/json" in tool_response.headers.get("content-type", "") else None
                                            if not test_json:
                                                # Parse SSE
                                                for line in tool_response.text.split('\n'):
                                                    if line.startswith('data: '):
                                                        test_json = json.loads(line[6:])
                                                        break
                                            
                                            if test_json and test_json.get("error", {}).get("code") == -32601:
                                                print("tools/list not found, trying Composio-specific methods...")
                                                
                                                # Try different possible methods
                                                alternative_methods = [
                                                    "composio/tools/list",
                                                    "composio.tools.list", 
                                                    "getTools",
                                                    "get_tools",
                                                    "listTools",
                                                    "list_tools"
                                                ]
                                                
                                                for alt_method in alternative_methods:
                                                    print(f"Trying method: {alt_method}")
                                                    alt_response = await client.post(
                                                        config.endpoint,
                                                        headers=tools_headers,
                                                        json={
                                                            "jsonrpc": "2.0",
                                                            "method": alt_method,
                                                            "params": {},
                                                            "id": 100 + alternative_methods.index(alt_method)
                                                        }
                                                    )
                                                    
                                                    # Check if this method works
                                                    try:
                                                        alt_json = alt_response.json() if "application/json" in alt_response.headers.get("content-type", "") else None
                                                        if not alt_json:
                                                            for line in alt_response.text.split('\n'):
                                                                if line.startswith('data: '):
                                                                    alt_json = json.loads(line[6:])
                                                                    break
                                                        
                                                        if alt_json and "result" in alt_json and "tools" in alt_json.get("result", {}):
                                                            print(f"Found working method: {alt_method}")
                                                            tool_response = alt_response
                                                            break
                                                        elif alt_json and not alt_json.get("error"):
                                                            print(f"Method {alt_method} returned: {json.dumps(alt_json, indent=2)[:200]}")
                                                    except:
                                                        pass
                                        except Exception as e:
                                            print(f"Error checking alternative methods: {e}")
                                    
                                    # Check if we got a "method not found" error
                                    try:
                                        test_result = tool_response.json()
                                        if test_result.get("error", {}).get("code") == -32601:
                                            print(f"tools/list not supported, trying mcp/list_tools...")
                                            # Try alternative method names
                                            tool_response = await client.post(
                                                config.endpoint,
                                                headers=tools_headers,  # Use tools_headers with session info
                                                json={"jsonrpc": "2.0", "method": "mcp/list_tools", "params": {}, "id": 3}
                                            )
                                            
                                            test_result = tool_response.json()
                                            if test_result.get("error", {}).get("code") == -32601:
                                                print(f"mcp/list_tools not supported, trying listTools...")
                                                tool_response = await client.post(
                                                    config.endpoint,
                                                    headers=tools_headers,  # Use tools_headers with session info
                                                    json={"jsonrpc": "2.0", "method": "listTools", "params": {}, "id": 4}
                                                )
                                                
                                                test_result = tool_response.json()
                                                if test_result.get("error", {}).get("code") == -32601:
                                                    print(f"listTools not supported, trying list...")
                                                    tool_response = await client.post(
                                                        config.endpoint,
                                                        headers=tools_headers,  # Use tools_headers with session info
                                                        json={"jsonrpc": "2.0", "method": "list", "params": {}, "id": 5}
                                                    )
                                    except:
                                        pass
                                    print(f"🔧 tools/list response status: {tool_response.status_code}")
                                    print(f"🔧 tools/list response headers: {dict(tool_response.headers)}")
                                    print(f"🔧 tools/list content-type: {tool_response.headers.get('content-type', 'unknown')}")
                                    print(f"🔧 tools/list response length: {len(tool_response.text)} chars")
                                    print(f"🔧 tools/list response first 1000 chars: {tool_response.text[:1000]}")
                                    
                                    # Check if it's an SSE response
                                    if tool_response.headers.get("content-type", "").startswith("text/event-stream"):
                                        print(f"🔧 tools/list returned SSE response - will parse in Composio section")
                                    
                                    if tool_response.status_code >= 400:
                                        print(f"🔧 HTTP error response for tools/list")
                                    else:
                                        print(f"🔧 tools/list completed, checking for JSON-RPC errors")
                                except httpx.HTTPError as e:
                                    print(f"HTTP error fetching tools from {server}: {e}")
                                    print(f"Request URL: {config.endpoint}")
                                    if hasattr(e, 'response') and e.response:
                                        print(f"Error response: {e.response.text[:500]}")
                                    server_tools = []
                                    tool_response = None
                                except Exception as e:
                                    print(f"🔧 Unexpected error in tools/list: {type(e).__name__}: {str(e)}")
                                    import traceback
                                    print(f"🔧 Traceback: {traceback.format_exc()}")
                                    server_tools = []
                                    tool_response = None
                                
                                # Check if it's actually an error response
                                if tool_response is None:
                                    print(f"🔧 tool_response is None, skipping to next server")
                                    server_tools = []
                                elif tool_response.status_code >= 400:
                                    print(f"Tool fetch failed for {server}: {tool_response.text[:200]}")
                                    server_tools = []
                                # Handle Composio's response (might be SSE or regular JSON)
                                elif is_composio:
                                    # Check if it's SSE or regular JSON
                                    if tool_response.headers.get("content-type", "").startswith("text/event-stream"):
                                        # Parse SSE - improved parser for large responses
                                        print(f"🔧 Parsing SSE response, size: {len(tool_response.text)} chars")
                                        text = tool_response.text
                                        result = None
                                        
                                        # Try to parse the SSE response more robustly
                                        lines = text.split('\n')
                                        print(f"🔧 SSE has {len(lines)} lines")
                                        
                                        for i, line in enumerate(lines):
                                            if line.startswith('data: '):
                                                data = line[6:]  # Remove 'data: ' prefix
                                                print(f"🔧 Line {i}: data length = {len(data)}")
                                                try:
                                                    result = json.loads(data)
                                                    print(f"🔧 Successfully parsed JSON from line {i}")
                                                    if "result" in result and "tools" in result["result"]:
                                                        tools_count = len(result["result"]["tools"])
                                                        print(f"🔧 Found {tools_count} tools in response")
                                                    break
                                                except json.JSONDecodeError as e:
                                                    print(f"🔧 JSON parse error on line {i}: {str(e)[:100]}")
                                                    continue
                                                except Exception as e:
                                                    print(f"🔧 Other parse error on line {i}: {str(e)[:100]}")
                                                    continue
                                        
                                        if not result:
                                            print(f"🔧 Failed to parse any valid JSON from SSE response")
                                            print(f"🔧 First 500 chars: {text[:500]}")
                                            print(f"🔧 Last 500 chars: {text[-500:]}")
                                            server_tools = []
                                        else:
                                            print(f"🔧 Successfully parsed SSE response, result type: {type(result)}")
                                            print(f"🔧 Result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
                                    else:
                                        # Regular JSON response
                                        try:
                                            result = tool_response.json()
                                        except:
                                            result = None
                                    
                                    # Check for JSON-RPC error
                                    if result and "error" in result:
                                        print(f"🔧 JSON-RPC error from {server}: {result['error']}")
                                        error_code = result["error"].get("code")
                                        print(f"🔧 Error code: {error_code}, Type: {type(error_code)}")
                                        
                                        # For Composio, if tools/list fails, use hardcoded tools
                                        if error_code == -32601:  # Method not found
                                            print(f"🔧 Composio MCP doesn't support standard tools/list")
                                            print(f"🔧 Using hardcoded tool definitions for Composio")
                                        else:
                                            print(f"🔧 Different error code ({error_code}), not using hardcoded tools")
                                    elif result and "result" in result:
                                        print(f"🔧 tools/list returned success result: {json.dumps(result.get('result', {}), indent=2)[:500]}")
                                        # Extract the tools from the JSON-RPC result
                                        if "tools" in result["result"]:
                                            server_tools = result["result"]["tools"]
                                            print(f"🔧 Successfully extracted {len(server_tools)} tools from tools/list response")
                                        else:
                                            print(f"🔧 No 'tools' field in result, keys: {list(result['result'].keys())}")
                                            server_tools = []
                                    else:
                                        print(f"🔧 Unexpected tools/list response format: {result}")
                                        server_tools = []
                        
                        print(f"Server {server}: Found {len(server_tools)} tools")
                        
                        if not server_tools:
                            print(f"No tools to process for {server}")
                            continue
                        
                        print(f"Processing {len(server_tools)} tools for {server}")
                        tools_added_count = 0
                        
                        # Check if this is from the API fallback (tools already have inputSchema)
                        skip_processing = False
                        if server_tools and "inputSchema" in server_tools[0]:
                            print(f"Tools from API fallback already formatted, adding directly")
                            skip_processing = True
                        
                        for i, tool in enumerate(server_tools):
                            if i < 2:  # Log first 2 tools for debugging
                                try:
                                    print(f"Tool {i}: {json.dumps(tool, indent=2)[:300]}")
                                except:
                                    print(f"Tool {i}: Could not serialize, keys: {tool.keys() if isinstance(tool, dict) else 'not a dict'}")
                            
                            # If tools are from API fallback, they're already formatted
                            if skip_processing:
                                # Tools from API already have the right structure
                                tool_name = tool.get('name', 'unknown_tool')
                                # Clean the name to match Anthropic's requirements
                                clean_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in tool_name)
                                clean_server = server.replace('-', '_')
                                full_name = f"{clean_server}__{clean_name}"
                                if len(full_name) > 128:
                                    full_name = full_name[:128]
                                
                                # Get the schema - it's already in inputSchema
                                params = tool.get("inputSchema", {})
                                if not isinstance(params, dict):
                                    params = {"type": "object", "properties": {}}
                                elif "type" not in params:
                                    params["type"] = "object"
                                if params.get("type") == "object" and "properties" not in params:
                                    params["properties"] = {}
                                
                                tool_def = {
                                    "type": "function",
                                    "function": {
                                        "name": full_name,
                                        "description": f"[{server}] {tool.get('description', '')}",
                                        "parameters": params
                                    }
                                }
                                tools.append(tool_def)
                                tools_added_count += 1
                                
                                if i < 5:
                                    print(f"Added API tool: {full_name}")
                                continue
                            
                            # Convert to OpenAI tools format
                            # Get the input schema from various possible locations
                            params = tool.get("inputSchema", tool.get("input_schema", tool.get("parameters", {})))
                            
                            # Ensure we have a valid schema structure
                            if not params:
                                params = {"type": "object", "properties": {}}
                            elif not isinstance(params, dict):
                                params = {"type": "object", "properties": {}}
                            elif "type" not in params:
                                params["type"] = "object"
                            
                            # Ensure object types have properties
                            if params.get("type") == "object" and "properties" not in params:
                                params["properties"] = {}
                            
                            # Clean up the tool name to match Anthropic's requirements
                            # Must match pattern '^[a-zA-Z0-9_-]{1,128}$'
                            # Replace any invalid characters with underscores
                            tool_name = tool.get('name', 'unknown_tool')
                            # Remove or replace invalid characters
                            clean_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in tool_name)
                            # Ensure server prefix is also clean
                            clean_server = server.replace('-', '_')
                            full_name = f"{clean_server}__{clean_name}"
                            # Truncate if too long
                            if len(full_name) > 128:
                                full_name = full_name[:128]
                            
                            tool_def = {
                                "type": "function",
                                "function": {
                                    "name": full_name,
                                    "description": f"[{server}] {tool.get('description', '')}",
                                    "parameters": params
                                }
                            }
                            tools.append(tool_def)
                            tools_added_count += 1
                            
                            # Log tool being added
                            if i < 5:  # Log first 5 tools
                                print(f"Added tool: {full_name}")
                        
                        print(f"Added {tools_added_count} tools from {server} to final list")
                    except Exception as e:
                        print(f"Error getting tools for {server}: {e}")
                        continue
            
            # Deduplicate tools by name
            seen_names = set()
            unique_tools = []
            for tool in tools:
                tool_name = tool["function"]["name"]
                if tool_name not in seen_names:
                    seen_names.add(tool_name)
                    unique_tools.append(tool)
                else:
                    print(f"Skipping duplicate tool: {tool_name}")
            
            tools = unique_tools
            print(f"Total unique tools: {len(tools)}")
            
            # Limit tools if there are too many (to avoid overloading the API)
            max_tools = 50  # Anthropic can handle many tools, but let's be reasonable
            if len(tools) > max_tools:
                print(f"Warning: {len(tools)} tools exceeds limit of {max_tools}, truncating...")
                # Prioritize Composio tools (Gmail, etc) by keeping those that start with "composio"
                composio_tools = [t for t in tools if t["function"]["name"].startswith("composio")]
                other_tools = [t for t in tools if not t["function"]["name"].startswith("composio")]
                
                # Take all Composio tools first, then fill with others
                tools = composio_tools[:max_tools]
                if len(tools) < max_tools:
                    tools.extend(other_tools[:max_tools - len(tools)])
                
                print(f"Reduced to {len(tools)} tools (prioritizing Composio services)")
            
            # Format messages for the model
            llm_messages = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in messages
            ]
            
            # Add system message about available Gmail tools if present
            gmail_tools = [t for t in tools if "GMAIL" in t["function"]["name"]]
            if gmail_tools:
                gmail_tool_names = [t["function"]["name"].replace("composio_gmail__", "") for t in gmail_tools[:5]]
                system_msg = f"You have access to {len(gmail_tools)} Gmail tools including: {', '.join(gmail_tool_names)}... Use these tools to help the user with their email tasks."
                print(f"🔧 Adding Gmail tools system message: {system_msg}")
                # Insert at the beginning if no system message, or append to first system message
                if llm_messages and llm_messages[0]["role"] == "system":
                    llm_messages[0]["content"] += f"\n\n{system_msg}"
                else:
                    llm_messages.insert(0, {"role": "system", "content": system_msg})
            
            # Call the model using any-llm for all providers
            try:
                if tools:
                    await websocket.send_json({
                        "type": "status",
                        "message": f"Using {model} via any-llm with {len(tools)} tools"
                    })
                else:
                    await websocket.send_json({
                        "type": "status",
                        "message": f"Using {model} via any-llm"
                    })
                
                # Use any-llm for all model calls (with or without tools)
                max_retries = 3
                retry_delay = 1
                response = None
                
                # Debug: Log the tools being sent to the model
                if tools:
                    print(f"🔧 Sending {len(tools)} tools to model {model}")
                    for i, tool in enumerate(tools[:3]):  # Log first 3 tools
                        print(f"🔧 Tool {i}: {tool['function']['name']}")
                else:
                    print(f"🔧 No tools being sent to model {model}")
                
                for attempt in range(max_retries):
                    try:
                        response = await asyncio.to_thread(
                            completion,
                            model=model,
                            messages=llm_messages,
                            tools=tools if tools else None,
                            max_tokens=4096
                        )
                        break  # Success, exit retry loop
                    except Exception as e:
                        error_str = str(e)
                        print(f"Error calling model (attempt {attempt + 1}/{max_retries}): {e}")
                        
                        # Check if it's a 529 overloaded error
                        if "529" in error_str or "overloaded" in error_str.lower():
                            if attempt < max_retries - 1:
                                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                                print(f"API overloaded, retrying in {wait_time} seconds...")
                                await websocket.send_json({
                                    "type": "status",
                                    "message": f"API overloaded, retrying in {wait_time}s..."
                                })
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                # Final attempt failed
                                await websocket.send_json({
                                    "type": "error",
                                    "message": "The API is currently overloaded. Please try again in a moment."
                                })
                                return
                        
                        # For other errors, log and raise
                        if tools:
                            print(f"Number of tools: {len(tools)}")
                            print(f"First tool: {json.dumps(tools[0], indent=2) if tools else 'No tools'}")
                        raise
                
                if response is None:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to get response from model after retries"
                    })
                    return
                
                # Multi-round tool execution loop
                max_tool_rounds = 5  # Prevent infinite loops
                tool_round = 0
                
                while tool_round < max_tool_rounds:
                    tool_round += 1
                    print(f"🔧 Tool execution round {tool_round}/{max_tool_rounds}")
                    
                    # Debug: Log the response structure
                    print(f"🔧 Model response type: {type(response)}")
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    choice = response.choices[0]
                    print(f"🔧 Response content: {choice.message.content[:200]}...")
                    print(f"🔧 Response has tool_calls attr: {hasattr(choice.message, 'tool_calls')}")
                    if hasattr(choice.message, 'tool_calls'):
                        print(f"🔧 tool_calls value: {choice.message.tool_calls}")
                else:
                    print(f"🔧 No choices in response: {response}")
                
                # Check if response contains tool calls
                has_tool_calls = False
                tool_calls = []
                
                print(f"🔧 Checking for tool calls in response...")
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    choice = response.choices[0]
                    print(f"🔧 Response choice message has tool_calls: {hasattr(choice.message, 'tool_calls')}")
                    if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                        has_tool_calls = True
                        tool_calls = choice.message.tool_calls
                        print(f"🔧 Found {len(tool_calls)} tool calls!")
                    else:
                        print(f"🔧 No tool calls found in response")
                else:
                    print(f"🔧 No response choices found")
                        
                if has_tool_calls:
                    # Handle tool calls
                    await websocket.send_json({
                        "type": "status",
                        "message": f"Executing {len(tool_calls)} tool(s)"
                    })
                    
                    # Add assistant message with tool calls to conversation
                    tool_message = {
                        "role": "assistant",
                        "content": choice.message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in tool_calls
                        ]
                    }
                    llm_messages.append(tool_message)
                    
                    # Execute each tool
                    for tool_call in tool_calls:
                        print(f"🔧 Executing tool: {tool_call.function.name}")
                        # Parse server and tool name from the combined name
                        full_name = tool_call.function.name
                        print(f"🔧 Parsing tool name: {full_name}")
                        if "__" in full_name:
                            server_name, tool_name = full_name.split("__", 1)
                        else:
                            server_name = "unknown"
                            tool_name = full_name
                        print(f"🔧 Parsed server_name: {server_name}, tool_name: {tool_name}")
                        print(f"🔧 Available remote servers: {list(remote_mcp_servers.keys())}")
                        
                        # Handle server name mismatch (underscores vs hyphens)
                        actual_server_name = server_name
                        if server_name not in remote_mcp_servers:
                            # Try converting underscores to hyphens
                            hyphen_name = server_name.replace('_', '-')
                            if hyphen_name in remote_mcp_servers:
                                actual_server_name = hyphen_name
                                print(f"🔧 Using hyphen server name: {actual_server_name}")
                            else:
                                print(f"🔧 Server {server_name} not found in remote servers!")
                        
                        # Parse arguments
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except:
                            arguments = {}
                            
                        await websocket.send_json({
                            "type": "tool_call",
                            "server": actual_server_name,
                            "tool": tool_name,
                            "arguments": arguments
                        })
                        
                        # Execute tool (check if remote or local)
                        tool_result = {}
                        if actual_server_name in remote_mcp_servers:
                            # Remote server execution
                            config = remote_mcp_servers[actual_server_name]
                            print(f"🔧 Tool execution config endpoint: {config.endpoint}")
                            print(f"🔧 Tool execution config headers: {config.headers}")
                            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                                try:
                                    headers = config.headers.copy()
                                    is_composio = "composio" in config.endpoint
                                    
                                    if is_composio:
                                        headers["Accept"] = "application/json, text/event-stream"
                                        # Protocol version should already be in headers from negotiation
                                        if "Mcp-Protocol-Version" not in headers:
                                            headers["Mcp-Protocol-Version"] = "2025-03-26"  # Fallback
                                        # Debug: Check if we have session ID and protocol version
                                        if "Mcp-Session-Id" in headers:
                                            print(f"🔧 Tool execution with session ID: {headers['Mcp-Session-Id']} and protocol: {headers.get('Mcp-Protocol-Version', 'unknown')}")
                                        else:
                                            print(f"⚠️  Tool execution WITHOUT session ID for {server_name}")
                                    elif config.auth_token:
                                        headers["Authorization"] = f"Bearer {config.auth_token}"
                                    
                                    # For Composio Slack, try to extract user_id and add it to arguments
                                    if "slack" in server_name.lower() and is_composio:
                                        # Extract user_id from the endpoint URL if present
                                        import re
                                        user_id_match = re.search(r'user_id=([^&]+)', config.endpoint)
                                        if user_id_match:
                                            extracted_user_id = user_id_match.group(1)
                                            print(f"🔧 Extracted user_id from Slack endpoint: {extracted_user_id}")
                                            # Try adding entity_id to the arguments for Slack
                                            if not isinstance(arguments, dict):
                                                arguments = {}
                                            arguments["entity_id"] = extracted_user_id
                                            print(f"🔧 Added entity_id to Slack tool arguments: {extracted_user_id}")
                                    
                                    tool_request = {
                                        "jsonrpc": "2.0",
                                        "method": "tools/call",
                                        "params": {
                                            "name": tool_name,
                                            "arguments": arguments
                                        },
                                        "id": 1
                                    }
                                    print(f"🔧 Sending tool call request: {json.dumps(tool_request)}")
                                    
                                    tool_response = await client.post(
                                        config.endpoint,
                                        headers=headers,
                                        json=tool_request
                                    )
                                    
                                    print(f"🔧 Tool call response status: {tool_response.status_code}")
                                    print(f"🔧 Tool call response headers: {dict(tool_response.headers)}")
                                    print(f"🔧 Tool call response body (first 500 chars): {tool_response.text[:500]}")
                                    
                                    # Handle Composio SSE response
                                    if is_composio and tool_response.headers.get("content-type", "").startswith("text/event-stream"):
                                        text = tool_response.text
                                        result = None
                                        for line in text.split('\n'):
                                            if line.startswith('data: '):
                                                data = line[6:]
                                                try:
                                                    result = json.loads(data)
                                                    break
                                                except:
                                                    continue
                                        if not result:
                                            result = {"error": "Failed to parse SSE response"}
                                    else:
                                        result = tool_response.json()
                                    
                                    tool_result = result.get("result", {"error": "No result"})
                                    print(f"🔧 Tool result extracted: {json.dumps(tool_result, indent=2)[:500]}")
                                except Exception as e:
                                    print(f"🔧 Exception during tool execution: {type(e).__name__}: {str(e)}")
                                    tool_result = {"error": str(e)}
                        else:
                            # Local server via mcpd
                            async with httpx.AsyncClient() as client:
                                try:
                                    tool_response = await client.post(
                                        f"{MCPD_BASE_URL}/servers/{server_name}/tools/{tool_name}",
                                        json=arguments
                                    )
                                    tool_result = tool_response.json()
                                except Exception as e:
                                    tool_result = {"error": str(e)}
                        
                        await websocket.send_json({
                            "type": "tool_result",
                            "server": server_name,
                            "tool": tool_name,
                            "result": tool_result
                        })
                        
                        # Add tool result to conversation
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result)
                        }
                        print(f"🔧 Adding tool result to conversation: {tool_message['content'][:200]}...")
                        llm_messages.append(tool_message)
                    
                    # Continue conversation with tool results with retry logic
                    print(f"🔧 Calling model again with {len(llm_messages)} messages including tool results")
                    final_response = None
                    for attempt in range(max_retries):
                        try:
                            final_response = await asyncio.to_thread(
                                completion,
                                model=model,
                                messages=llm_messages,
                                max_tokens=4096
                            )
                            print(f"🔧 Got final response after tool execution")
                            break
                        except Exception as e:
                            error_str = str(e)
                            print(f"Error calling model after tools (attempt {attempt + 1}/{max_retries}): {e}")
                            
                            if "529" in error_str or "overloaded" in error_str.lower():
                                if attempt < max_retries - 1:
                                    wait_time = retry_delay * (2 ** attempt)
                                    print(f"API overloaded after tools, retrying in {wait_time} seconds...")
                                    await websocket.send_json({
                                        "type": "status",
                                        "message": f"API overloaded, retrying in {wait_time}s..."
                                    })
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": "The API is currently overloaded. Please try again in a moment."
                                    })
                                    return
                            raise
                    
                    if final_response is None:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Failed to get response after tool execution"
                        })
                        return
                    
                    # Check if final response has more tool calls
                    print(f"🔧 Checking if final response has more tool calls...")
                    
                    if hasattr(final_response, 'choices') and len(final_response.choices) > 0:
                        final_choice = final_response.choices[0]
                        
                        # Check for additional tool calls
                        if hasattr(final_choice.message, 'tool_calls') and final_choice.message.tool_calls:
                            print(f"🔧 Final response contains {len(final_choice.message.tool_calls)} MORE tool calls!")
                            # Set response to final_response to continue the loop
                            response = final_response
                            continue  # Go back to the beginning of the while True loop
                        
                        # No more tool calls, send the final message
                        final_text = final_choice.message.content
                        print(f"🔧 No more tool calls. Sending final response: {final_text[:200] if final_text else 'None'}...")
                    else:
                        final_text = str(final_response)
                        print(f"🔧 Using str(final_response): {final_text[:200]}...")
                    
                    if not final_text:
                        print(f"🔧 WARNING: final_text is empty or None!")
                        final_text = "I completed the tool execution but couldn't generate a response. Please check the logs."
                    
                    final_message = {
                        "type": "message",
                        "role": "assistant",
                        "content": final_text,
                        "model": model
                    }
                    print(f"🔧 Sending final WebSocket message: {json.dumps(final_message)[:300]}...")
                    
                    await websocket.send_json(final_message)
                    print(f"🔧 Final response sent successfully")
                    break  # Exit the while True loop
                else:
                    # No tool calls, just send the message
                    response_text = ""
                    if hasattr(response, 'choices') and len(response.choices) > 0:
                        response_text = response.choices[0].message.content
                    elif hasattr(response, 'content'):
                        if isinstance(response.content, list) and len(response.content) > 0:
                            response_text = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])
                        else:
                            response_text = str(response.content)
                    elif isinstance(response, str):
                        response_text = response
                    else:
                        response_text = str(response)
                    
                    await websocket.send_json({
                        "type": "message",
                        "role": "assistant",
                        "content": response_text,
                        "model": model
                    })
                    break  # Exit the tool rounds loop
                    
                # End of tool rounds loop
                if tool_round >= max_tool_rounds:
                    print(f"🔧 Reached maximum tool rounds ({max_tool_rounds})")
                    await websocket.send_json({
                        "type": "message",
                        "role": "assistant",
                        "content": "I've reached the maximum number of tool execution rounds. The task may be incomplete.",
                        "model": model
                    })
                    
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error calling {model}: {str(e)}"
                })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


# Config-related classes and functions
class ServerRequiredConfig(BaseModel):
    name: str
    package: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    required_env: List[str] = Field(default_factory=list)
    required_args: List[str] = Field(default_factory=list)
    required_args_bool: List[str] = Field(default_factory=list)

class ServerRuntimeConfig(BaseModel):
    name: str
    env: Dict[str, str] = Field(default_factory=dict)
    args: List[str] = Field(default_factory=list)

class ServerConfigDetail(BaseModel):
    required: ServerRequiredConfig
    runtime: ServerRuntimeConfig

class SetEnvRequest(BaseModel):
    server: str
    env: Dict[str, str]

class SetArgsRequest(BaseModel):
    server: str
    args: List[str] = Field(default_factory=list)
    replace: bool = True

class MCPServerInfo(BaseModel):
    name: str
    package: str
    description: str
    category: str
    required_env: List[str] = Field(default_factory=list)
    required_args: List[str] = Field(default_factory=list)
    example_args: List[str] = Field(default_factory=list)
    installed: bool = False

class InstallServerRequest(BaseModel):
    name: str
    package: str
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)

class RemoteServerConfig(BaseModel):
    name: str
    endpoint: str
    auth_token: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    
class QuickAddRequest(BaseModel):
    input: str  # Can be npm package, URL, or server name
    env: Dict[str, str] = Field(default_factory=dict)
    args: List[str] = Field(default_factory=list)

# Store remote MCP servers (in production, persist to database)
remote_mcp_servers: Dict[str, RemoteServerConfig] = {}

# Store MCP server UUID mappings: key = "{user_id}:{app_name}", value = server_uuid
# In production, use a database
mcp_server_mappings: Dict[str, str] = {}

def _default_config_paths():
    cfg_env = os.getenv("MCPD_CONFIG_FILE")
    if cfg_env:
        project_cfg = Path(cfg_env).expanduser()
    else:
        project_cfg = Path(__file__).resolve().parents[2] / ".mcpd.toml"
    
    rt_env = os.getenv("MCPD_RUNTIME_FILE")
    if rt_env:
        runtime_cfg = Path(rt_env).expanduser()
    else:
        xdg_config = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        runtime_cfg = Path(xdg_config) / "mcpd" / "secrets.dev.toml"
    
    return project_cfg, runtime_cfg

def _load_config_with_key(path: Path, key: str):
    if not path.exists():
        return {}
    try:
        with open(path, 'rb') as f:
            return tomli.load(f)
    except Exception:
        return {}

def _load_env(runtime_cfg: Path, server_name: str) -> Dict[str, str]:
    runtime_data = _load_config_with_key(runtime_cfg, "servers")
    servers = runtime_data.get("servers", {})
    server_config = servers.get(server_name, {})
    return server_config.get("env", {})

def _update_env_toml(runtime_cfg: Path, server_name: str, env: Dict[str, str]):
    runtime_cfg.parent.mkdir(parents=True, exist_ok=True)
    
    existing = {}
    if runtime_cfg.exists():
        with open(runtime_cfg, 'rb') as f:
            existing = tomli.load(f)
    
    if "servers" not in existing:
        existing["servers"] = {}
    if server_name not in existing["servers"]:
        existing["servers"][server_name] = {}
    
    existing["servers"][server_name]["env"] = env
    
    with open(runtime_cfg, 'w') as f:
        toml.dump(existing, f)

@app.get("/config/server/{server_name}")
async def get_server_config(server_name: str) -> ServerConfigDetail:
    """Get configuration details for a specific server"""
    project_cfg, runtime_cfg = _default_config_paths()
    
    # Load project config to get required fields
    project_data = _load_config_with_key(project_cfg, "servers")
    servers = project_data.get("servers", [])
    
    server_config = None
    for s in servers:
        if s.get("name") == server_name:
            server_config = s
            break
    
    if not server_config:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    # Create required config
    required = ServerRequiredConfig(
        name=server_name,
        package=server_config.get("package"),
        tools=server_config.get("tools", []),
        required_env=server_config.get("required_env", []),
        required_args=server_config.get("required_args", []),
        required_args_bool=server_config.get("required_args_bool", [])
    )
    
    # Load runtime config
    runtime_env = _load_env(runtime_cfg, server_name)
    runtime_args = server_config.get("args", [])
    
    runtime = ServerRuntimeConfig(
        name=server_name,
        env=runtime_env,
        args=runtime_args
    )
    
    return ServerConfigDetail(required=required, runtime=runtime)


@app.post("/config/env")
async def set_server_env(request: SetEnvRequest):
    """Set environment variables for a server"""
    _, runtime_cfg = _default_config_paths()
    _update_env_toml(runtime_cfg, request.server, request.env)
    return {"status": "success", "message": f"Environment updated for {request.server}"}

# Server marketplace/registry
MCP_SERVER_REGISTRY = [
    MCPServerInfo(
        name="filesystem",
        package="npx::@modelcontextprotocol/server-filesystem@latest",
        description="Read and write files on your local filesystem",
        category="Core",
        required_args=["path"],
        example_args=["/tmp/mcp-test-directory"]
    ),
    MCPServerInfo(
        name="github",
        package="npx::@modelcontextprotocol/server-github@latest",
        description="Interact with GitHub repositories, issues, and pull requests",
        category="Development",
        required_env=["GITHUB_TOKEN"]
    ),
    MCPServerInfo(
        name="gitlab",
        package="npx::@modelcontextprotocol/server-gitlab@latest",
        description="Interact with GitLab repositories and merge requests",
        category="Development",
        required_env=["GITLAB_TOKEN", "GITLAB_URL"]
    ),
    MCPServerInfo(
        name="git",
        package="npx::@modelcontextprotocol/server-git@latest",
        description="Execute git commands in a repository",
        category="Development",
        required_args=["repository"],
        example_args=["."]
    ),
    MCPServerInfo(
        name="sqlite",
        package="npx::@modelcontextprotocol/server-sqlite@latest",
        description="Query and modify SQLite databases",
        category="Data",
        required_args=["database"],
        example_args=["./database.db"]
    ),
    MCPServerInfo(
        name="postgres",
        package="npx::@modelcontextprotocol/server-postgres@latest",
        description="Query and modify PostgreSQL databases",
        category="Data",
        required_env=["DATABASE_URL"]
    ),
    MCPServerInfo(
        name="slack",
        package="npx::@modelcontextprotocol/server-slack@latest",
        description="Send messages and interact with Slack workspaces",
        category="Communication",
        required_env=["SLACK_TOKEN"]
    ),
    MCPServerInfo(
        name="google-drive",
        package="npx::@modelcontextprotocol/server-google-drive@latest",
        description="Access and manage Google Drive files",
        category="Storage",
        required_env=["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]
    ),
    MCPServerInfo(
        name="aws",
        package="npx::@modelcontextprotocol/server-aws@latest",
        description="Interact with AWS services",
        category="Cloud",
        required_env=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]
    ),
    MCPServerInfo(
        name="docker",
        package="npx::@modelcontextprotocol/server-docker@latest",
        description="Manage Docker containers and images",
        category="Infrastructure"
    ),
    MCPServerInfo(
        name="kubernetes",
        package="npx::@modelcontextprotocol/server-kubernetes@latest",
        description="Manage Kubernetes clusters and resources",
        category="Infrastructure",
        required_env=["KUBECONFIG"]
    ),
    MCPServerInfo(
        name="puppeteer",
        package="npx::@modelcontextprotocol/server-puppeteer@latest",
        description="Browser automation and web scraping",
        category="Web"
    ),
    MCPServerInfo(
        name="fetch",
        package="npx::@modelcontextprotocol/server-fetch@latest",
        description="Make HTTP requests and fetch web content",
        category="Web"
    ),
    MCPServerInfo(
        name="jupyter",
        package="npx::@modelcontextprotocol/server-jupyter@latest",
        description="Execute code in Jupyter notebooks",
        category="Data Science",
        required_args=["notebook"],
        example_args=["./notebook.ipynb"]
    ),
    MCPServerInfo(
        name="notion",
        package="npx::@modelcontextprotocol/server-notion@latest",
        description="Access and modify Notion pages and databases",
        category="Productivity",
        required_env=["NOTION_API_KEY"]
    ),
    MCPServerInfo(
        name="memory",
        package="npx::@modelcontextprotocol/server-memory@latest",
        description="Store and retrieve information across conversations",
        category="Core"
    ),
    MCPServerInfo(
        name="time",
        package="npx::@modelcontextprotocol/server-time@latest",
        description="Get current time and date information",
        category="Utilities"
    ),
    MCPServerInfo(
        name="weather",
        package="npx::@modelcontextprotocol/server-weather@latest",
        description="Get weather information and forecasts",
        category="Utilities",
        required_env=["WEATHER_API_KEY"]
    )
]

@app.get("/mcp-registry")
async def get_mcp_registry():
    """MCPD removed - return empty registry"""
    # MCPD has been removed, so local MCP servers won't work
    # Users should add remote MCP servers instead (like Composio)
    return []

@app.post("/install-mcp-server")
async def install_mcp_server(request: InstallServerRequest):
    """Install an MCP server using mcpd add command"""
    try:
        # Determine mcpd command path based on environment
        mcpd_cmd = "/usr/local/bin/mcpd" if os.getenv("CLOUD_MODE") == "true" else "mcpd"
        
        # Build the mcpd add command
        print(f"Installing server {request.name} with package {request.package}")
        # MCPD expects just the server name, not the full package
        # The package is resolved from registry
        cmd = [mcpd_cmd, "add", request.name]
        
        # TODO: After adding, we need to update the config with args
        # Arguments are stored in the config file, not passed to add command
        
        # Run the command  
        project_root = Path(__file__).resolve().parents[2]
        # In cloud mode, run from /root where mcpd config is
        cwd = "/root" if os.getenv("CLOUD_MODE") == "true" else str(project_root)
        print(f"Running command: {' '.join(cmd)} in directory: {cwd}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        
        print(f"Command stdout: {result.stdout}")
        print(f"Command stderr: {result.stderr}")
        print(f"Command return code: {result.returncode}")
        
        if result.returncode != 0 and "duplicate server name" not in result.stderr:
            raise HTTPException(status_code=500, detail=f"Failed to install server: {result.stderr}")
        
        # After adding the server, we need to configure its arguments
        if request.args:
            print(f"Configuring server {request.name} with args: {request.args}")
            # MCPD uses a secrets.toml file for runtime args
            # Try both paths - cloud mode uses /root, local mode uses user's home
            if os.getenv("CLOUD_MODE") == "true":
                secrets_path = Path("/root/.config/mcpd/secrets.toml")
            else:
                secrets_path = Path.home() / ".config" / "mcpd" / "secrets.toml"
            
            secrets_path.parent.mkdir(parents=True, exist_ok=True)
            
            import toml
            secrets = {}
            if secrets_path.exists():
                with open(secrets_path, 'r') as f:
                    secrets = toml.load(f)
            
            # MCPD expects the args directly under [servers.servername]
            # Not nested under an "args" key
            if "servers" not in secrets:
                secrets["servers"] = {}
            
            # Create the server section with args list directly
            secrets["servers"][request.name] = {
                "args": request.args  # This is the correct format MCPD expects
            }
            
            # Write back the secrets file
            with open(secrets_path, 'w') as f:
                toml.dump(secrets, f)
            print(f"Updated secrets.toml at {secrets_path} for server {request.name} with args: {request.args}")
        
        # If env vars are provided, save them to runtime config
        if request.env:
            _, runtime_cfg = _default_config_paths()
            _update_env_toml(runtime_cfg, request.name, request.env)
        
        return {"status": "success", "message": f"Server {request.name} installed successfully"}
        
    except subprocess.SubprocessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to run mcpd command: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/uninstall-mcp-server/{server_name}")
async def uninstall_mcp_server(server_name: str):
    """Uninstall an MCP server by removing it from config"""
    try:
        project_cfg, _ = _default_config_paths()
        
        if not project_cfg.exists():
            raise HTTPException(status_code=404, detail="Config file not found")
        
        # Load config
        with open(project_cfg, 'rb') as f:
            config = tomli.load(f)
        
        # Remove server from config
        servers = config.get("servers", [])
        config["servers"] = [s for s in servers if s.get("name") != server_name]
        
        # Write updated config
        with open(project_cfg, 'w') as f:
            toml.dump(config, f)
        
        return {"status": "success", "message": f"Server {server_name} uninstalled"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/mcpd-config")
async def debug_mcpd_config():
    """Debug endpoint to see MCPD config files"""
    import toml
    result = {}
    
    # Check config.toml
    config_path = Path("/root/.config/mcpd/config.toml")
    if config_path.exists():
        with open(config_path, 'r') as f:
            result["config.toml"] = toml.load(f)
    else:
        result["config.toml"] = "Not found"
    
    # Check secrets.toml
    secrets_path = Path("/root/.config/mcpd/secrets.toml")
    if secrets_path.exists():
        with open(secrets_path, 'r') as f:
            result["secrets.toml"] = toml.load(f)
    else:
        result["secrets.toml"] = "Not found"
    
    # List all files in mcpd config dir
    config_dir = Path("/root/.config/mcpd")
    if config_dir.exists():
        result["files"] = [str(f.relative_to(config_dir)) for f in config_dir.iterdir()]
    else:
        result["files"] = "Directory not found"
    
    return result

@app.post("/remove-server/{name}")
async def remove_server(name: str):
    """Remove a server from mcpd config to fix issues"""
    try:
        import toml
        removed = False
        
        # Remove from config.toml
        config_path = Path("/root/.config/mcpd/config.toml")
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = toml.load(f)
            
            # Remove the server
            if "servers" in config:
                config["servers"] = [s for s in config["servers"] if s.get("name") != name]
                removed = True
            
            # Write back the config
            with open(config_path, 'w') as f:
                toml.dump(config, f)
        
        # Also remove from secrets.toml
        secrets_path = Path("/root/.config/mcpd/secrets.toml")
        if secrets_path.exists():
            with open(secrets_path, 'r') as f:
                secrets = toml.load(f)
            
            if "servers" in secrets and name in secrets["servers"]:
                del secrets["servers"][name]
                removed = True
            
            with open(secrets_path, 'w') as f:
                toml.dump(secrets, f)
        
        if removed:
            return {"status": "success", "message": f"Server {name} removed"}
        return {"status": "error", "message": "Server not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/restart-mcpd")
async def restart_mcpd():
    """Restart the mcpd daemon to pick up config changes"""
    try:
        # Kill existing mcpd process (try pkill first, then supervisorctl)
        try:
            subprocess.run(["pkill", "-f", "mcpd daemon"], capture_output=True, check=False)
        except FileNotFoundError:
            # If pkill doesn't exist, try supervisorctl
            try:
                subprocess.run(["supervisorctl", "restart", "mcpd"], capture_output=True, check=False)
            except:
                pass
        await asyncio.sleep(1)
        
        # Start mcpd daemon again - set working directory to project root
        project_root = Path(__file__).resolve().parents[2]
        mcpd_cmd = "/usr/local/bin/mcpd" if os.getenv("CLOUD_MODE") == "true" else "mcpd"
        subprocess.Popen([mcpd_cmd, "daemon", "--dev"], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL,
                        cwd=str(project_root))
        await asyncio.sleep(2)
        
        return {"status": "success", "message": "mcpd restarted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/quick-add-server")
async def quick_add_server(request: QuickAddRequest):
    """Quick add a server from various input formats"""
    input_str = request.input.strip()
    
    # Detect input type
    if input_str.startswith(("http://", "https://")):
        # Remote HTTP endpoint
        # Extract name from URL or generate one
        import re
        from urllib.parse import urlparse
        
        parsed = urlparse(input_str)
        # Try to extract a name from the URL
        name_match = re.search(r'/([^/]+)(?:/mcp)?(?:\?|$)', parsed.path)
        if name_match:
            server_name = name_match.group(1)
        else:
            server_name = parsed.hostname or "remote-server"
        
        # Check for auth token in URL
        auth_token = None
        endpoint = input_str
        
        # For Composio, keep the customerId in the URL
        if "composio" in input_str:
            # Composio uses customerId in URL, not separate auth
            # Keep the full URL including query parameters
            endpoint = input_str
        elif "token=" in input_str:
            # Other services might use token parameter
            token_match = re.search(r'token=([^&]+)', input_str)
            if token_match:
                auth_token = token_match.group(1)
                # Remove token from URL for security
                endpoint = input_str.split("?")[0]
        else:
            # For other services, use base URL
            endpoint = input_str.split("?")[0]
        
        # Store remote server configuration
        remote_mcp_servers[server_name] = RemoteServerConfig(
            name=server_name,
            endpoint=endpoint,
            auth_token=auth_token,
            headers={"Content-Type": "application/json"}
        )
        
        return {
            "status": "success",
            "message": f"Added remote MCP server: {server_name}",
            "type": "remote",
            "name": server_name
        }
    
    elif input_str.startswith("npm:") or input_str.startswith("npx:"):
        # NPM package
        package = input_str.replace("npm:", "").replace("npx:", "").strip()
        # Extract server name from package
        server_name = package.split("/")[-1].replace("@latest", "").replace("server-", "")
        
        # Install via mcpd
        mcpd_cmd = "/usr/local/bin/mcpd" if os.getenv("CLOUD_MODE") == "true" else "mcpd"
        cmd = [mcpd_cmd, "add", server_name, f"npx::{package}"]
        if request.args:
            for arg in request.args:
                cmd.extend(["--arg", arg])
        
        project_root = Path(__file__).resolve().parents[2]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to install: {result.stderr}")
        
        # Save env vars if provided
        if request.env:
            _, runtime_cfg = _default_config_paths()
            _update_env_toml(runtime_cfg, server_name, request.env)
        
        return {
            "status": "success",
            "message": f"Installed local MCP server: {server_name}",
            "type": "local",
            "name": server_name
        }
    
    elif input_str.startswith("@") or "/" in input_str:
        # Likely an npm package name like @modelcontextprotocol/server-github
        package = input_str if input_str.startswith("npx::") else f"npx::{input_str}@latest"
        server_name = input_str.split("/")[-1].replace("@latest", "").replace("server-", "")
        
        # Install via mcpd
        mcpd_cmd = "/usr/local/bin/mcpd" if os.getenv("CLOUD_MODE") == "true" else "mcpd"
        cmd = [mcpd_cmd, "add", server_name, package]
        if request.args:
            for arg in request.args:
                cmd.extend(["--arg", arg])
        
        project_root = Path(__file__).resolve().parents[2]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to install: {result.stderr}")
        
        # Save env vars if provided
        if request.env:
            _, runtime_cfg = _default_config_paths()
            _update_env_toml(runtime_cfg, server_name, request.env)
        
        return {
            "status": "success",
            "message": f"Installed local MCP server: {server_name}",
            "type": "local",
            "name": server_name
        }
    
    else:
        # Try to find in registry
        for server in MCP_SERVER_REGISTRY:
            if server.name == input_str:
                # Install from registry
                mcpd_cmd = "/usr/local/bin/mcpd" if os.getenv("CLOUD_MODE") == "true" else "mcpd"
                cmd = [mcpd_cmd, "add", server.name, server.package]
                if request.args or server.example_args:
                    for arg in (request.args or server.example_args):
                        cmd.extend(["--arg", arg])
                
                print(f"Running command: {' '.join(cmd)}")
                # Set working directory to project root
                project_root = Path(__file__).resolve().parents[2]
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))
                print(f"Command output: {result.stdout}")
                print(f"Command stderr: {result.stderr}")
                if result.returncode != 0:
                    raise HTTPException(status_code=500, detail=f"Failed to install: {result.stderr}")
                
                # Save env vars
                if request.env or server.required_env:
                    _, runtime_cfg = _default_config_paths()
                    env_to_save = request.env or {k: "" for k in server.required_env}
                    _update_env_toml(runtime_cfg, server.name, env_to_save)
                
                return {
                    "status": "success",
                    "message": f"Installed {server.name} from registry",
                    "type": "local",
                    "name": server.name
                }
        
        raise HTTPException(status_code=400, detail=f"Could not determine how to add: {input_str}")

@app.post("/clear-mcp-mapping/{user_id}/{app_name}")
async def clear_mcp_mapping(user_id: str, app_name: str):
    """Clear a specific MCP server mapping to force recreation"""
    mapping_key = f"{user_id}:{app_name}"
    if mapping_key in mcp_server_mappings:
        old_id = mcp_server_mappings[mapping_key]
        del mcp_server_mappings[mapping_key]
        return {"status": "success", "message": f"Cleared mapping for {mapping_key} (was {old_id})"}
    return {"status": "not_found", "message": f"No mapping found for {mapping_key}"}

@app.delete("/remove-server/{server_name}")
async def remove_server(server_name: str):
    """Remove a server (local or remote)"""
    # Check if it's a remote server
    if server_name in remote_mcp_servers:
        del remote_mcp_servers[server_name]
        
        # Also clear from mcp_server_mappings if it's a Composio server
        if server_name.startswith("composio-"):
            # Find and remove any mappings that point to this server
            keys_to_remove = []
            for key, value in mcp_server_mappings.items():
                # Check if this mapping is for the server we're removing
                if server_name.endswith(key.split(':')[1]):  # Match app name
                    keys_to_remove.append(key)
                    print(f"Clearing mapping for {key} -> {value}")
            
            for key in keys_to_remove:
                del mcp_server_mappings[key]
        
        return {"status": "success", "message": f"Removed remote server: {server_name}"}
    
    # Otherwise try to remove from mcpd
    return await uninstall_mcp_server(server_name)