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

load_dotenv()

app = FastAPI(title="MCP Test Client API - Multi-Model")

# Import config if it exists, otherwise use defaults
try:
    from app.config import ALLOWED_ORIGINS, MCPD_ENABLED, MCPD_BASE_URL, MCPD_HEALTH_CHECK_URL
except ImportError:
    ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]
    MCPD_ENABLED = os.getenv("MCPD_ENABLED", "true").lower() == "true"
    MCPD_BASE_URL = os.getenv("MCPD_BASE_URL", "http://localhost:8090/api/v1")
    MCPD_HEALTH_CHECK_URL = os.getenv("MCPD_HEALTH_CHECK_URL", "http://localhost:8090/health")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
    
    if not MCPD_ENABLED:
        print("MCPD is disabled in configuration")
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
    return {
        "status": "healthy",
        "mcpd_available": mcpd_available,
        "mcpd_url": MCPD_BASE_URL if mcpd_available else None
    }


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
    
    # Get local servers from mcpd (only if available)
    if mcpd_available:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{MCPD_BASE_URL}/servers")
                response.raise_for_status()
                local_servers = response.json()
                # Mark these as local servers
                servers.extend([{"name": s, "type": "local"} for s in local_servers])
        except httpx.HTTPError:
            pass  # mcpd might not be running
    
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                headers = config.headers.copy()
                
                # Check if it's Composio (they use SSE)
                is_composio = "composio" in config.endpoint
                if is_composio:
                    headers["Accept"] = "application/json, text/event-stream"
                    # Composio expects customerId in URL, not auth header
                elif config.auth_token:
                    headers["Authorization"] = f"Bearer {config.auth_token}"
                
                # Call remote server's tool listing endpoint
                response = await client.post(
                    config.endpoint,
                    headers=headers,
                    json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
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
            if available_servers and model.startswith("anthropic/"):
                for server in available_servers:
                    try:
                        # Check if it's a remote server or local
                        if server in remote_mcp_servers:
                            # Use the get_server_tools endpoint for remote servers
                            response = await get_server_tools(server)
                            server_tools = response.get("tools", [])
                        else:
                            # Local server via mcpd
                            async with httpx.AsyncClient() as client:
                                response = await client.get(f"{MCPD_BASE_URL}/servers/{server}/tools")
                                if response.status_code == 200:
                                    server_tools = response.json().get("tools", [])
                                else:
                                    server_tools = []
                        
                        print(f"Server {server}: Found {len(server_tools)} tools")
                        
                        for tool in server_tools:
                            # Convert to OpenAI tools format
                            # Ensure parameters have properties field if type is object
                            params = tool.get("inputSchema", {})
                            if params.get("type") == "object" and "properties" not in params:
                                params["properties"] = {}
                            
                            tool_def = {
                                "type": "function",
                                "function": {
                                    "name": f"{server}__{tool['name']}",
                                    "description": f"[{server}] {tool.get('description', '')}",
                                    "parameters": params
                                }
                            }
                            tools.append(tool_def)
                    except Exception as e:
                        print(f"Error getting tools for {server}: {e}")
                        continue
            
            print(f"Total tools gathered: {len(tools)}")
            
            # Format messages for the model
            llm_messages = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in messages
            ]
            
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
                try:
                    response = await asyncio.to_thread(
                        completion,
                        model=model,
                        messages=llm_messages,
                        tools=tools if tools else None,
                        max_tokens=4096
                    )
                except Exception as e:
                    print(f"Error calling model: {e}")
                    if tools:
                        print(f"Tools passed: {json.dumps(tools[:1], indent=2)}")  # Print first tool for debugging
                    raise
                
                # Check if response contains tool calls
                has_tool_calls = False
                tool_calls = []
                
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    choice = response.choices[0]
                    if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                        has_tool_calls = True
                        tool_calls = choice.message.tool_calls
                        
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
                        # Parse server and tool name from the combined name
                        full_name = tool_call.function.name
                        if "__" in full_name:
                            server_name, tool_name = full_name.split("__", 1)
                        else:
                            server_name = "unknown"
                            tool_name = full_name
                            
                        # Parse arguments
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except:
                            arguments = {}
                            
                        await websocket.send_json({
                            "type": "tool_call",
                            "server": server_name,
                            "tool": tool_name,
                            "arguments": arguments
                        })
                        
                        # Execute tool (check if remote or local)
                        tool_result = {}
                        if server_name in remote_mcp_servers:
                            # Remote server execution
                            config = remote_mcp_servers[server_name]
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                try:
                                    headers = config.headers.copy()
                                    is_composio = "composio" in config.endpoint
                                    
                                    if is_composio:
                                        headers["Accept"] = "application/json, text/event-stream"
                                    elif config.auth_token:
                                        headers["Authorization"] = f"Bearer {config.auth_token}"
                                    
                                    tool_response = await client.post(
                                        config.endpoint,
                                        headers=headers,
                                        json={
                                            "jsonrpc": "2.0",
                                            "method": "tools/call",
                                            "params": {
                                                "name": tool_name,
                                                "arguments": arguments
                                            },
                                            "id": 1
                                        }
                                    )
                                    
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
                                except Exception as e:
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
                        llm_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result)
                        })
                    
                    # Continue conversation with tool results
                    final_response = await asyncio.to_thread(
                        completion,
                        model=model,
                        messages=llm_messages,
                        max_tokens=4096
                    )
                    
                    # Send final response
                    if hasattr(final_response, 'choices') and len(final_response.choices) > 0:
                        final_text = final_response.choices[0].message.content
                    else:
                        final_text = str(final_response)
                        
                    await websocket.send_json({
                        "type": "message",
                        "role": "assistant",
                        "content": final_text,
                        "model": model
                    })
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
    """Get list of available MCP servers from registry"""
    # Check which servers are already installed
    project_cfg, _ = _default_config_paths()
    installed_servers = set()
    
    if project_cfg.exists():
        try:
            with open(project_cfg, 'rb') as f:
                config = tomli.load(f)
                servers = config.get("servers", [])
                installed_servers = {s.get("name") for s in servers}
        except:
            pass
    
    # Mark installed servers
    registry = []
    for server in MCP_SERVER_REGISTRY:
        server_copy = server.model_copy()
        server_copy.installed = server.name in installed_servers
        registry.append(server_copy)
    
    return registry

@app.post("/install-mcp-server")
async def install_mcp_server(request: InstallServerRequest):
    """Install an MCP server using mcpd add command"""
    try:
        # Build the mcpd add command
        cmd = ["mcpd", "add", request.name, request.package]
        
        # Add arguments if provided
        if request.args:
            for arg in request.args:
                cmd.extend(["--arg", arg])
        
        # Run the command
        project_root = Path(__file__).resolve().parents[2]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to install server: {result.stderr}")
        
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

@app.post("/restart-mcpd")
async def restart_mcpd():
    """Restart the mcpd daemon to pick up config changes"""
    try:
        # Kill existing mcpd process
        subprocess.run(["pkill", "-f", "mcpd daemon"], capture_output=True)
        await asyncio.sleep(1)
        
        # Start mcpd daemon again - set working directory to project root
        project_root = Path(__file__).resolve().parents[2]
        subprocess.Popen(["mcpd", "daemon", "--dev"], 
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
        cmd = ["mcpd", "add", server_name, f"npx::{package}"]
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
        cmd = ["mcpd", "add", server_name, package]
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
                cmd = ["mcpd", "add", server.name, server.package]
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

@app.delete("/remove-server/{server_name}")
async def remove_server(server_name: str):
    """Remove a server (local or remote)"""
    # Check if it's a remote server
    if server_name in remote_mcp_servers:
        del remote_mcp_servers[server_name]
        return {"status": "success", "message": f"Removed remote server: {server_name}"}
    
    # Otherwise try to remove from mcpd
    return await uninstall_mcp_server(server_name)