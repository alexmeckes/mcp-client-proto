from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import httpx
import json
import asyncio
from anthropic import AsyncAnthropic
import os
from dotenv import load_dotenv
import tomli
import toml
from pathlib import Path
from any_llm import completion
import openai
import subprocess

load_dotenv()

app = FastAPI(title="MCP Test Client API - Multi-Model")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MCPD_BASE_URL = os.getenv("MCPD_BASE_URL", "http://localhost:8090/api/v1")

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

# Keep the anthropic client for tool usage
anthropic_client = None
if ANTHROPIC_API_KEY:
    try:
        anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        print(f"Warning: Could not initialize Anthropic client: {e}")
        anthropic_client = None


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
            supports_tools=True
        ),
        ModelInfo(
            id="anthropic/claude-opus-4-20250514",
            name="Claude Opus 4",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True
        ),
        ModelInfo(
            id="anthropic/claude-sonnet-4-20250514",
            name="Claude Sonnet 4",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True
        ),
        # Claude 3.7
        ModelInfo(
            id="anthropic/claude-3-7-sonnet-20250219",
            name="Claude Sonnet 3.7",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True
        ),
        # Claude 3.5 models
        ModelInfo(
            id="anthropic/claude-3-5-sonnet-20241022",
            name="Claude 3.5 Sonnet v2",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True
        ),
        ModelInfo(
            id="anthropic/claude-3-5-sonnet-20240620",
            name="Claude 3.5 Sonnet",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True
        ),
        ModelInfo(
            id="anthropic/claude-3-5-haiku-20241022",
            name="Claude 3.5 Haiku",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True
        ),
        # Claude 3 models
        ModelInfo(
            id="anthropic/claude-3-haiku-20240307",
            name="Claude 3 Haiku",
            provider="anthropic",
            requires_key=True,
            is_available=bool(user_api_keys.get("anthropic")),
            supports_tools=True
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
    global user_api_keys, anthropic_client
    
    user_api_keys.update(request.keys)
    
    # Update environment variables for any-llm
    if "anthropic" in request.keys and request.keys["anthropic"]:
        os.environ["ANTHROPIC_API_KEY"] = request.keys["anthropic"]
        anthropic_client = AsyncAnthropic(api_key=request.keys["anthropic"])
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
    
    # Get local servers from mcpd
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


@app.get("/servers/{server_name}/tools")
async def get_server_tools(server_name: str):
    """Get tools for a specific MCP server (local or remote)"""
    # Check if it's a remote server
    if server_name in remote_mcp_servers:
        config = remote_mcp_servers[server_name]
        async with httpx.AsyncClient() as client:
            try:
                headers = config.headers.copy()
                if config.auth_token:
                    headers["Authorization"] = f"Bearer {config.auth_token}"
                
                # Call remote server's tool listing endpoint
                response = await client.post(
                    config.endpoint,
                    headers=headers,
                    json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
                )
                response.raise_for_status()
                result = response.json()
                
                # Extract tools from JSON-RPC response
                if "result" in result:
                    return {"tools": result["result"].get("tools", [])}
                return {"tools": []}
            except httpx.HTTPError as e:
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
            
            # Update API keys if provided
            if api_keys:
                for key, value in api_keys.items():
                    if value:
                        user_api_keys[key] = value
                        if key == "anthropic":
                            os.environ["ANTHROPIC_API_KEY"] = value
                            global anthropic_client
                            anthropic_client = AsyncAnthropic(api_key=value)
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
                        async with httpx.AsyncClient() as client:
                            response = await client.get(f"{MCPD_BASE_URL}/servers/{server}/tools")
                            if response.status_code == 200:
                                server_tools = response.json().get("tools", [])
                                for tool in server_tools:
                                    tools.append({
                                        "name": f"{server}__{tool['name']}",
                                        "description": f"[{server}] {tool.get('description', '')}",
                                        "input_schema": tool.get("inputSchema", {})
                                    })
                    except:
                        continue
            
            # Format messages for the model
            llm_messages = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in messages
            ]
            
            # Call the model
            try:
                if tools and model.startswith("anthropic/"):
                    # Use Anthropic client for tool-enabled calls
                    if not anthropic_client:
                        try:
                            # Try to create client without any extra kwargs that might cause issues
                            import inspect
                            sig = inspect.signature(AsyncAnthropic.__init__)
                            params = sig.parameters
                            kwargs = {"api_key": user_api_keys["anthropic"]}
                            anthropic_client = AsyncAnthropic(**kwargs)
                        except Exception as e:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Failed to initialize Anthropic client: {str(e)}"
                            })
                            continue
                    
                    await websocket.send_json({
                        "type": "status",
                        "message": f"Using {model} with {len(tools)} tools from {len(available_servers)} servers"
                    })
                    
                    # Extract model name after "anthropic/"
                    model_name = model.split("/")[1] if "/" in model else model
                    
                    try:
                        response = await anthropic_client.messages.create(
                            model=model_name,
                            messages=llm_messages,
                            max_tokens=4096,
                            tools=tools if tools else None
                        )
                    except Exception as api_error:
                        # If model doesn't exist or other API error, fall back to any-llm
                        await websocket.send_json({
                            "type": "status", 
                            "message": f"Anthropic API error, trying with any-llm: {str(api_error)}"
                        })
                        
                        response = await asyncio.to_thread(
                            completion,
                            model=model,
                            messages=llm_messages
                        )
                        
                        # Extract text content from response
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
                        continue
                    
                    # Process Anthropic response with tools
                    await websocket.send_json({
                        "type": "message",
                        "role": "assistant",
                        "content": response.content[0].text if hasattr(response.content[0], 'text') else "",
                        "model": model
                    })
                    
                    # Handle tool calls
                    for content in response.content:
                        if hasattr(content, 'type') and content.type == 'tool_use':
                            server_name, tool_name = content.name.split("__", 1)
                            
                            await websocket.send_json({
                                "type": "tool_call",
                                "server": server_name,
                                "tool": tool_name,
                                "arguments": content.input
                            })
                            
                            # Execute tool (check if remote or local)
                            if server_name in remote_mcp_servers:
                                # Remote server execution
                                config = remote_mcp_servers[server_name]
                                async with httpx.AsyncClient() as client:
                                    try:
                                        headers = config.headers.copy()
                                        if config.auth_token:
                                            headers["Authorization"] = f"Bearer {config.auth_token}"
                                        
                                        tool_response = await client.post(
                                            config.endpoint,
                                            headers=headers,
                                            json={
                                                "jsonrpc": "2.0",
                                                "method": "tools/call",
                                                "params": {
                                                    "name": tool_name,
                                                    "arguments": content.input
                                                },
                                                "id": 1
                                            }
                                        )
                                        result = tool_response.json()
                                        tool_result = result.get("result", {"error": "No result"})
                                        
                                        await websocket.send_json({
                                            "type": "tool_result",
                                            "server": server_name,
                                            "tool": tool_name,
                                            "result": tool_result
                                        })
                                    except Exception as e:
                                        await websocket.send_json({
                                            "type": "tool_result",
                                            "server": server_name,
                                            "tool": tool_name,
                                            "result": {"error": str(e)}
                                        })
                            else:
                                # Local server via mcpd
                                async with httpx.AsyncClient() as client:
                                    try:
                                        tool_response = await client.post(
                                            f"{MCPD_BASE_URL}/servers/{server_name}/tools/{tool_name}",
                                            json=content.input
                                        )
                                        tool_result = tool_response.json()
                                        
                                        await websocket.send_json({
                                            "type": "tool_result",
                                            "server": server_name,
                                            "tool": tool_name,
                                            "result": tool_result
                                        })
                                    except Exception as e:
                                        await websocket.send_json({
                                            "type": "tool_result",
                                            "server": server_name,
                                            "tool": tool_name,
                                            "result": {"error": str(e)}
                                        })
                else:
                    # Use any-llm for non-tool calls
                    await websocket.send_json({
                        "type": "status",
                        "message": f"Using {model} (no tool support)"
                    })
                    
                    response = await asyncio.to_thread(
                        completion,
                        model=model,
                        messages=llm_messages
                    )
                    
                    # Extract text content from response
                    if hasattr(response, 'choices') and len(response.choices) > 0:
                        # OpenAI-style response
                        response_text = response.choices[0].message.content
                    elif hasattr(response, 'content'):
                        # Anthropic-style response
                        if isinstance(response.content, list) and len(response.content) > 0:
                            response_text = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])
                        else:
                            response_text = str(response.content)
                    elif isinstance(response, str):
                        # Direct string response
                        response_text = response
                    else:
                        # Fallback - try to get any text we can
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
        result = subprocess.run(cmd, capture_output=True, text=True)
        
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
        
        # Start mcpd daemon again
        subprocess.Popen(["mcpd", "daemon", "--dev"], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
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
        if "token=" in input_str:
            token_match = re.search(r'token=([^&]+)', input_str)
            if token_match:
                auth_token = token_match.group(1)
        elif "customerId=" in input_str:
            # Composio-style URL
            auth_token = input_str.split("customerId=")[1].split("&")[0]
        
        # Store remote server configuration
        remote_mcp_servers[server_name] = RemoteServerConfig(
            name=server_name,
            endpoint=input_str.split("?")[0],  # Base URL without params
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
        
        result = subprocess.run(cmd, capture_output=True, text=True)
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
        
        result = subprocess.run(cmd, capture_output=True, text=True)
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
                
                result = subprocess.run(cmd, capture_output=True, text=True)
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