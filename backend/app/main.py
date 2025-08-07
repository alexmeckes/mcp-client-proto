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

load_dotenv()

app = FastAPI(title="MCP Test Client API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MCPD_BASE_URL = os.getenv("MCPD_BASE_URL", "http://localhost:8090/api/v1")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is required")

anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    server: Optional[str] = None


class ServerInfo(BaseModel):
    name: str
    status: str
    tools: Optional[List[Dict[str, Any]]] = None


# -----------------
# Config UI models
# -----------------

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


def _default_config_paths():
    # Project `.mcpd.toml` — allow override via env, else try repo root
    cfg_env = os.getenv("MCPD_CONFIG_FILE")
    if cfg_env:
        project_cfg = Path(cfg_env).expanduser()
    else:
        # backend/app/main.py → repo_root/.mcpd.toml
        project_cfg = Path(__file__).resolve().parents[2] / ".mcpd.toml"

    # Runtime secrets — allow override via env, else XDG/HOME
    rt_env = os.getenv("MCPD_RUNTIME_FILE")
    if rt_env:
        runtime_cfg = Path(rt_env).expanduser()
    else:
        xdg = os.getenv("XDG_CONFIG_HOME")
        if xdg:
            runtime_cfg = Path(xdg).expanduser() / "mcpd" / "secrets.dev.toml"
        else:
            runtime_cfg = Path.home() / ".config" / "mcpd" / "secrets.dev.toml"

    return project_cfg, runtime_cfg


def _load_project_config() -> Dict[str, Any]:
    project_cfg, _ = _default_config_paths()
    if not project_cfg.exists():
        return {"servers": []}
    with project_cfg.open("rb") as f:
        data = tomli.load(f)
    data.setdefault("servers", [])
    return data


def _load_runtime_config() -> Dict[str, Any]:
    _, runtime_cfg = _default_config_paths()
    if not runtime_cfg.exists():
        return {"servers": {}}
    with runtime_cfg.open("rb") as f:
        data = tomli.load(f)
    data.setdefault("servers", {})
    return data


def _save_runtime_config(cfg: Dict[str, Any]) -> None:
    _, runtime_cfg = _default_config_paths()
    runtime_cfg.parent.mkdir(parents=True, exist_ok=True)
    # Ensure top-level structure
    cfg.setdefault("servers", {})
    tmp = runtime_cfg.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        toml.dump(cfg, f)
    # Move into place and restrict perms
    tmp.replace(runtime_cfg)
    try:
        os.chmod(runtime_cfg, 0o600)
    except Exception:
        pass


def _server_required_detail(entry: Dict[str, Any]) -> ServerRequiredConfig:
    return ServerRequiredConfig(
        name=str(entry.get("name", "")),
        package=entry.get("package"),
        tools=list(entry.get("tools", []) or []),
        required_env=list(entry.get("required_env", []) or []),
        required_args=list(entry.get("required_args", []) or []),
        required_args_bool=list(entry.get("required_args_bool", []) or []),
    )


def _server_runtime_detail(name: str, rt: Dict[str, Any]) -> ServerRuntimeConfig:
    servers = rt.get("servers", {}) or {}
    node = servers.get(name, {}) or {}
    env = dict(node.get("env", {}) or {})
    args = list(node.get("args", []) or [])
    return ServerRuntimeConfig(name=name, env=env, args=args)


@app.get("/config/servers", response_model=List[ServerConfigDetail])
async def list_config_servers():
    proj = _load_project_config()
    rt = _load_runtime_config()
    result: List[ServerConfigDetail] = []
    for entry in proj.get("servers", []):
        req = _server_required_detail(entry)
        run = _server_runtime_detail(req.name, rt)
        result.append(ServerConfigDetail(required=req, runtime=run))
    return result


@app.get("/config/server/{server_name}", response_model=ServerConfigDetail)
async def get_config_server(server_name: str):
    proj = _load_project_config()
    rt = _load_runtime_config()
    entry = next((s for s in proj.get("servers", []) if str(s.get("name")) == server_name), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found in project config")
    req = _server_required_detail(entry)
    run = _server_runtime_detail(server_name, rt)
    return ServerConfigDetail(required=req, runtime=run)


@app.post("/config/env")
async def set_config_env(payload: SetEnvRequest):
    rt = _load_runtime_config()
    servers = rt.setdefault("servers", {})
    node = servers.setdefault(payload.server, {})
    env = node.setdefault("env", {})
    env.update(payload.env or {})
    _save_runtime_config(rt)
    return {"status": "ok"}


@app.post("/config/args")
async def set_config_args(payload: SetArgsRequest):
    rt = _load_runtime_config()
    servers = rt.setdefault("servers", {})
    node = servers.setdefault(payload.server, {})
    current = list(node.get("args", []) or [])
    if payload.replace:
        node["args"] = list(payload.args or [])
    else:
        # merge unique while preserving current order
        seen = set(current)
        merged = current + [a for a in payload.args or [] if a not in seen]
        node["args"] = merged
    _save_runtime_config(rt)
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "MCP Test Client API", "status": "running"}


@app.get("/servers", response_model=List[str])
async def list_servers():
    """List all available MCP servers from mcpd"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MCPD_BASE_URL}/servers")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail=f"Failed to connect to mcpd: {str(e)}")


@app.get("/servers/{server_name}/tools")
async def get_server_tools(server_name: str):
    """Get available tools for a specific MCP server"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{MCPD_BASE_URL}/servers/{server_name}/tools")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail=f"Failed to get tools: {str(e)}")


@app.post("/servers/{server_name}/tools/{tool_name}")
async def call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any] = {}):
    """Call a specific tool on an MCP server"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{MCPD_BASE_URL}/servers/{server_name}/tools/{tool_name}",
                json=arguments
            )
            response.raise_for_status()
            return {"result": response.json()}
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail=f"Failed to call tool: {str(e)}")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with Claude"""
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_json()
            messages = data.get("messages", [])
            available_servers = data.get("available_servers", [])
            
            tools = []
            if available_servers:
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
            
            anthropic_messages = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in messages
            ]
            
            if tools:
                await websocket.send_json({
                    "type": "status",
                    "message": f"Claude has access to {len(tools)} tools from {len(available_servers)} servers"
                })
                
                response = await anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4096,
                    messages=anthropic_messages,
                    tools=tools
                )
                
                await websocket.send_json({
                    "type": "message",
                    "role": "assistant",
                    "content": response.content[0].text if response.content and hasattr(response.content[0], 'text') else ""
                })
                
                if response.content and len(response.content) > 0:
                    for content_block in response.content:
                        if hasattr(content_block, 'type') and content_block.type == 'tool_use':
                            server_name, tool_name = content_block.name.split("__", 1)
                            
                            await websocket.send_json({
                                "type": "tool_call",
                                "tool": tool_name,
                                "server": server_name,
                                "arguments": content_block.input
                            })
                            
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                try:
                                    tool_response = await client.post(
                                        f"{MCPD_BASE_URL}/servers/{server_name}/tools/{tool_name}",
                                        json=content_block.input
                                    )
                                    tool_result = tool_response.json() if tool_response.status_code == 200 else {"error": f"Tool call failed: {tool_response.text}"}
                                except Exception as e:
                                    tool_result = {"error": str(e)}
                            
                            await websocket.send_json({
                                "type": "tool_result",
                                "tool": tool_name,
                                "server": server_name,
                                "result": tool_result
                            })
            else:
                response = await anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4096,
                    messages=anthropic_messages
                )
                
                await websocket.send_json({
                    "type": "message",
                    "role": "assistant",
                    "content": response.content[0].text if response.content else ""
                })
                
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })