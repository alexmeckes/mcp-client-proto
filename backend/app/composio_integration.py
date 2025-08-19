"""Proper Composio integration using their SDK"""
import os
import json
from typing import Optional, List, Dict, Any
from composio import Composio, ComposioToolSet
from composio.client.exceptions import ComposioClientError
import uuid
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class ComposioIntegration:
    """Handle Composio tool connections and authentication"""
    
    def __init__(self):
        # Get Composio API key from environment
        self.api_key = os.getenv("COMPOSIO_API_KEY", "")
        if self.api_key:
            self.client = Composio(api_key=self.api_key)
            self.toolset = ComposioToolSet(api_key=self.api_key)
        else:
            self.client = None
            self.toolset = None
            logger.warning("No COMPOSIO_API_KEY found. Composio features will be disabled.")
    
    def is_configured(self) -> bool:
        """Check if Composio is properly configured"""
        return self.client is not None
    
    async def initiate_connection(self, user_id: str, app_name: str, callback_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Initiate connection for a specific app (GitHub, Slack, etc.)
        
        Args:
            user_id: Unique identifier for the user
            app_name: Name of the app to connect (github, slack, notion, etc.)
            callback_url: Optional callback URL after auth completes
        
        Returns:
            Dict with redirect_url for OAuth flow
        """
        if not self.is_configured():
            return {"error": "Composio not configured. Please set COMPOSIO_API_KEY environment variable."}
        
        try:
            # Create or get entity for this user
            entity = self.client.get_entity(id=user_id)
            
            # First, get or create an auth config for this app
            # This ensures we have a proper auth_config_id for MCP server creation
            auth_config_id = None
            try:
                # Try to get the default Composio auth config
                from composio.client.collections import AuthConfigManager
                auth_manager = AuthConfigManager(self.client)
                
                # Get existing auth configs for the app
                auth_configs = auth_manager.get(app=app_name.upper())
                if auth_configs and len(auth_configs) > 0:
                    auth_config_id = auth_configs[0].id
                    logger.info(f"Using existing auth config: {auth_config_id}")
                else:
                    # Create a new auth config using Composio's managed auth
                    new_config = auth_manager.create(
                        app=app_name.upper(),
                        use_composio_auth=True
                    )
                    auth_config_id = new_config.id if hasattr(new_config, 'id') else None
                    logger.info(f"Created new auth config: {auth_config_id}")
            except Exception as e:
                logger.warning(f"Could not get/create auth config: {e}")
                # Continue without auth_config_id - will use Composio defaults
            
            # Initiate connection for the specific app
            # If we have an auth_config_id, use it
            if auth_config_id:
                connection_request = entity.initiate_connection(
                    app_name=app_name.upper(),
                    redirect_url=callback_url,
                    auth_config_id=auth_config_id  # Specify which auth config to use
                )
            else:
                # Fallback to default
                connection_request = entity.initiate_connection(
                    app_name=app_name.upper(),
                    redirect_url=callback_url
                )
            
            # Store the auth_config_id for later use
            if auth_config_id and user_id and app_name:
                # Store in a class variable for retrieval after OAuth
                if not hasattr(self, 'auth_config_mapping'):
                    self.auth_config_mapping = {}
                self.auth_config_mapping[f"{user_id}:{app_name}"] = auth_config_id
            
            return {
                "redirect_url": connection_request.redirectUrl,
                "connection_id": connection_request.connectedAccountId if hasattr(connection_request, 'connectedAccountId') else None,
                "auth_config_id": auth_config_id,  # Include auth_config_id
                "user_id": user_id,
                "app": app_name
            }
            
        except Exception as e:
            logger.error(f"Failed to initiate connection: {e}")
            return {"error": str(e)}
    
    async def get_user_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all connected apps for a user
        
        Args:
            user_id: User identifier
        
        Returns:
            List of connected apps with their status
        """
        if not self.is_configured():
            return []
        
        try:
            entity = self.client.get_entity(id=user_id)
            connections = entity.get_connections()
            
            result = []
            for conn in connections:
                # Log the actual connection object to understand its structure
                # Check all available attributes
                conn_dict = {}
                if hasattr(conn, '__dict__'):
                    conn_dict = conn.__dict__
                    logger.info(f"Connection attributes: {list(conn_dict.keys())}")
                
                # Try to find auth_config_id
                auth_config_id = None
                if hasattr(conn, 'authConfigId'):
                    auth_config_id = conn.authConfigId
                elif hasattr(conn, 'auth_config_id'):
                    auth_config_id = conn.auth_config_id
                elif hasattr(conn, 'authConfig'):
                    auth_config_id = conn.authConfig
                
                logger.info(f"Connection: app={conn.appName if hasattr(conn, 'appName') else 'N/A'}, "
                          f"id={conn.id if hasattr(conn, 'id') else 'N/A'}, "
                          f"auth_config_id={auth_config_id}")
                
                result.append({
                    "app": conn.appName if hasattr(conn, 'appName') else None,
                    "status": conn.status if hasattr(conn, 'status') else None,
                    "connected_at": conn.createdAt if hasattr(conn, 'createdAt') else None,
                    "connection_id": conn.id if hasattr(conn, 'id') else None,
                    "auth_config_id": auth_config_id  # Add auth_config_id to result
                })
            
            return result
        except Exception as e:
            logger.error(f"Failed to get connections: {e}")
            return []
    
    async def get_available_tools(self, user_id: str, app_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available tools for a user's connected apps
        
        Args:
            user_id: User identifier
            app_name: Optional filter for specific app
        
        Returns:
            List of available tools
        """
        if not self.api_key:
            logger.error("Composio API key not configured")
            return []
        
        try:
            import httpx
            
            # Use the REST API directly since SDK method is unclear
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            # Build query parameters
            # Start with no params to see what we get
            params = {}
            
            # Only add filtering if we have an app name
            # Note: The Composio API might not support these filters
            # We'll filter client-side if needed
            if app_name:
                # Log that we're attempting to filter
                logger.info(f"Attempting to filter for app: {app_name}")
            
            logger.info(f"Requesting tools with params: {params} (filtering for {app_name} will be done client-side)")
            
            async with httpx.AsyncClient() as client:
                # Try entity-specific endpoint first if we have a user_id
                if user_id and app_name:
                    # Try entity-specific tools endpoint
                    entity_url = f"https://backend.composio.dev/api/v1/entity/{user_id}/tools"
                    logger.info(f"Trying entity-specific endpoint: {entity_url}")
                    try:
                        response = await client.get(
                            entity_url,
                            headers=headers,
                            params={"appName": app_name.upper()},
                            timeout=30.0
                        )
                        if response.status_code == 200:
                            logger.info("Successfully got tools from entity endpoint")
                        else:
                            logger.info(f"Entity endpoint returned {response.status_code}, falling back to general endpoint")
                            response = None
                    except Exception as e:
                        logger.info(f"Entity endpoint failed: {e}, falling back to general endpoint")
                        response = None
                else:
                    response = None
                
                # Fallback to general tools endpoint
                if response is None or response.status_code != 200:
                    # Try v3 API first, then fallback to v1
                    url = "https://backend.composio.dev/api/v3/tools"
                    logger.info(f"Calling: {url} with params: {params}")
                    response = await client.get(
                        url,
                        headers=headers,
                        params=params,
                        timeout=30.0
                    )
                    
                    # If v3 fails, try v1
                    if response.status_code == 404:
                        logger.info("v3 API not found, trying v1...")
                        response = await client.get(
                            "https://backend.composio.dev/api/v1/tools",
                            headers=headers,
                            params=params,
                            timeout=30.0
                        )
                
                logger.info(f"API response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"API response keys: {data.keys()}")
                    logger.info(f"API response type: {type(data)}")
                    
                    # Handle if response is a list directly
                    if isinstance(data, list):
                        tools = data
                        logger.info(f"Response is a list with {len(tools)} tools")
                    else:
                        # Try different possible response formats
                        tools = data.get("items", data.get("tools", data.get("data", [])))
                    
                    # Log the raw response structure for debugging
                    if not tools and data:
                        logger.info(f"Raw API response (first 500 chars): {str(data)[:500]}")
                    
                    result = []
                    # Log first few tools to see what we're getting
                    for i, tool in enumerate(tools):
                        if i < 3:
                            logger.info(f"Tool {i}: name={tool.get('name')}, app={tool.get('app')}, appName={tool.get('appName')}")
                        
                        # Check if this tool belongs to the requested app
                        tool_app = tool.get("app", tool.get("appName", "")).lower()
                        if app_name and tool_app != app_name.lower():
                            # Skip tools from other apps
                            continue
                        
                        result.append({
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "app": tool.get("app", tool.get("appName", app_name or "")),
                            "parameters": tool.get("parameters", tool.get("input_schema", {}))
                        })
                    
                    # Log app distribution
                    apps_found = set(t["app"] for t in result) if result else set()
                    logger.info(f"Found {len(result)} tools for {app_name or 'all apps'}, apps present: {apps_found}")
                    
                    # If no tools found for the specific app, log all apps seen
                    if app_name and len(result) == 0:
                        all_apps = set(t.get("app", t.get("appName", "")).lower() for t in tools)
                        logger.warning(f"No tools found for {app_name}. Apps in response: {all_apps}")
                    
                    return result
                else:
                    logger.error(f"Failed to get tools: {response.status_code} - {response.text[:200]}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to get tools: {e}")
            return []
    
    async def execute_tool(self, user_id: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a Composio tool
        
        Args:
            user_id: User identifier
            tool_name: Name of the tool to execute
            params: Parameters for the tool
        
        Returns:
            Tool execution result
        """
        if not self.is_configured():
            return {"error": "Composio not configured"}
        
        try:
            # Execute tool through toolset
            result = self.toolset.execute_tool(
                tool_name=tool_name,
                params=params,
                entity_id=user_id
            )
            
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_or_create_auth_config(self, app_name: str) -> Optional[str]:
        """
        Get or create an auth config for an app.
        This is REQUIRED for MCP servers to expose tools.
        
        Returns:
            auth_config_id starting with 'ac_' or None
        """
        if not self.api_key:
            logger.error("No API key configured")
            return None
            
        try:
            import httpx
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                # First, try to get existing auth configs
                logger.info(f"Getting auth configs for {app_name}")
                
                # Try the auth-configs endpoint
                response = await client.get(
                    "https://backend.composio.dev/api/v1/auth-configs",
                    headers=headers,
                    params={"app": app_name.upper()},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Auth configs response: {json.dumps(data, indent=2)[:500]}")
                    
                    # Look for existing auth config
                    configs = data if isinstance(data, list) else data.get("items", data.get("data", []))
                    for config in configs:
                        config_id = config.get("id", config.get("authConfigId"))
                        if config_id and config_id.startswith("ac_"):
                            logger.info(f"Found existing auth config: {config_id}")
                            return config_id
                
                # If no existing config, create one
                logger.info(f"Creating new auth config for {app_name}")
                create_response = await client.post(
                    "https://backend.composio.dev/api/v1/auth-configs",
                    headers=headers,
                    json={
                        "app": app_name.upper(),
                        "useComposioAuth": True,  # Use Composio's managed OAuth
                        "name": f"{app_name} Auth Config"
                    },
                    timeout=30.0
                )
                
                if create_response.status_code in [200, 201]:
                    config = create_response.json()
                    config_id = config.get("id", config.get("authConfigId"))
                    if config_id and config_id.startswith("ac_"):
                        logger.info(f"Created new auth config: {config_id}")
                        return config_id
                    else:
                        logger.error(f"Created config but got invalid ID: {config_id}")
                else:
                    logger.error(f"Failed to create auth config: {create_response.status_code} - {create_response.text[:200]}")
                    
        except Exception as e:
            logger.error(f"Error getting/creating auth config: {e}")
            
        return None
    
    async def create_mcp_server(self, user_id: str, app_name: str) -> Optional[Dict[str, str]]:
        """
        Create an MCP server using Composio SDK (proper way)
        
        Args:
            user_id: User identifier (entity ID in Composio)
            app_name: Name of the app (gmail, slack, etc.)
        
        Returns:
            Dict with server_id and url, or None if failed
        """
        if not self.client:
            logger.error("Composio client not configured")
            return None
            
        try:
            # Get the user's connection for this app
            connections = await self.get_user_connections(user_id)
            connection_id = None
            auth_config_id = None
            
            for conn in connections:
                if conn.get("app", "").lower() == app_name.lower():
                    connection_id = conn.get("connection_id")
                    auth_config_id = conn.get("auth_config_id")
                    logger.info(f"Found connection for {app_name}: connection_id={connection_id}, auth_config_id={auth_config_id}")
                    break
            
            if not connection_id:
                logger.error(f"No connection found for {app_name}. User needs to connect the app first.")
                return None
            
            # Use the SDK to create MCP server properly
            # According to docs, we need to use the MCP module
            try:
                # Import MCP module from Composio SDK
                from composio.client.enums import App, Action
                
                # Get all Gmail actions/tools
                gmail_tools = [
                    "GMAIL_SEND_EMAIL",
                    "GMAIL_LIST_EMAILS",
                    "GMAIL_GET_EMAIL",
                    "GMAIL_REPLY_TO_EMAIL",
                    "GMAIL_CREATE_DRAFT",
                    "GMAIL_DELETE_EMAIL",
                    "GMAIL_MARK_EMAIL_AS_READ",
                    "GMAIL_MARK_EMAIL_AS_UNREAD",
                    "GMAIL_FORWARD_EMAIL",
                    "GMAIL_GET_PROFILE",
                    "GMAIL_SEARCH_EMAILS",
                    "GMAIL_ADD_LABEL",
                    "GMAIL_REMOVE_LABEL",
                    "GMAIL_CREATE_LABEL",
                    "GMAIL_LIST_LABELS"
                ]
                
                # Create server name
                server_name = f"{app_name}-{user_id[:8]}"
                
                # Check if MCP module exists in SDK
                if hasattr(self.client, 'mcp'):
                    logger.info(f"Creating MCP server using SDK for {app_name}")
                    
                    # Create the MCP server with proper configuration
                    server_config = [{
                        "authConfigId": auth_config_id or connection_id,  # Use auth config or connection
                        "allowedTools": gmail_tools if app_name.lower() == "gmail" else []
                    }]
                    
                    # Create the server
                    result = self.client.mcp.create(
                        server_name,
                        server_config,
                        {"isChatAuth": False}  # We already have auth
                    )
                    
                    if result:
                        logger.info(f"Created MCP server via SDK: {result}")
                        return {
                            "server_id": result.get("id", server_name),
                            "url": result.get("url", f"https://mcp.composio.dev/composio/server/{result.get('id')}/mcp")
                        }
                else:
                    logger.warning("MCP module not found in SDK, falling back to API method")
                    return await self.create_mcp_server_old(user_id, app_name)
                    
            except ImportError as e:
                logger.error(f"Failed to import Composio MCP modules: {e}")
                return await self.create_mcp_server_old(user_id, app_name)
            except Exception as e:
                logger.error(f"Failed to create MCP server via SDK: {e}")
                return await self.create_mcp_server_old(user_id, app_name)
                
        except Exception as e:
            logger.error(f"Failed to create MCP server: {e}")
            return None
    
    async def create_mcp_server_old(self, user_id: str, app_name: str) -> Optional[Dict[str, str]]:
        """
        Create an MCP server instance for a connected app via Composio API
        
        Args:
            user_id: User identifier (entity ID in Composio)
            app_name: Name of the app
        
        Returns:
            Dict with server_id and url, or None if failed
        """
        if not self.api_key:
            logger.error("Composio API key not configured")
            return None
            
        try:
            import httpx
            
            # Call Composio API to create MCP server
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            # First check if the user has this app connected and get auth_config_id
            logger.info(f"Creating MCP server for {app_name} with entity {user_id}")
            
            auth_config_id = None
            
            # CRITICAL: We MUST have a proper auth_config_id for tools to work
            # Always try to get or create one first
            logger.info(f"Ensuring we have proper auth_config_id for {app_name}")
            auth_config_id = await self.get_or_create_auth_config(app_name)
            
            if not auth_config_id or not auth_config_id.startswith("ac_"):
                logger.error(f"Failed to get proper auth_config_id for {app_name}")
                logger.error("Without auth_config_id, MCP server will have no tools!")
                # Try fallback methods
                
                # Check if we have a stored auth_config_id from OAuth initiation
                if hasattr(self, 'auth_config_mapping'):
                    mapping_key = f"{user_id}:{app_name}"
                    if mapping_key in self.auth_config_mapping:
                        auth_config_id = self.auth_config_mapping[mapping_key]
                        logger.info(f"Using stored auth_config_id from OAuth: {auth_config_id}")
                
                # If still not found, check connections
                if not auth_config_id or not auth_config_id.startswith("ac_"):
                    connections = await self.get_user_connections(user_id)
                    logger.info(f"Found {len(connections)} connections for user")
                    
                    for conn in connections:
                        conn_app = conn.get("app") or conn.get("appName") or ""
                        if conn_app.lower() == app_name.lower():
                            # Look for auth_config_id
                            possible_fields = ["auth_config_id", "authConfigId", "auth_config", "authConfig"]
                            for field in possible_fields:
                                if field in conn and conn[field] and str(conn[field]).startswith("ac_"):
                                    auth_config_id = conn[field]
                                    logger.info(f"Found auth_config_id in connection: {auth_config_id}")
                                    break
                            
                            if not auth_config_id or not auth_config_id.startswith("ac_"):
                                # Last resort - use connection ID (won't work for tools)
                                connection_id = conn.get("connection_id") or conn.get("id")
                                logger.error(f"No proper auth_config_id found! Using connection_id: {connection_id}")
                                logger.error("WARNING: Server will be created but tools won't work!")
                                auth_config_id = connection_id
                            break
            
            if not auth_config_id:
                # Try to get or create auth config for the app
                logger.warning(f"No auth_config_id found in connections, attempting to fetch/create one")
                
                try:
                    # First, try to get the default Composio auth config for the app
                    # This is what gets used when you do OAuth through Composio
                    async with httpx.AsyncClient() as client:
                        # Get auth configs using the Composio SDK approach
                        logger.info(f"Getting default auth config for {app_name}")
                        
                        # Try using the SDK to get the auth config
                        if self.client:
                            try:
                                # Get the default auth config using Composio SDK
                                from composio.client.collections import AuthConfigManager
                                auth_manager = AuthConfigManager(self.client)
                                
                                # Get or create default auth config for the app
                                auth_configs = auth_manager.get(app=app_name.upper())
                                if auth_configs and len(auth_configs) > 0:
                                    auth_config_id = auth_configs[0].id if hasattr(auth_configs[0], 'id') else None
                                    logger.info(f"Found auth config via SDK: {auth_config_id}")
                            except Exception as e:
                                logger.error(f"SDK approach failed: {e}")
                        
                        # If SDK didn't work, try API
                        if not auth_config_id:
                            # Try to get existing auth configs via API
                            auth_response = await client.get(
                                f"https://backend.composio.dev/api/v1/auth-configs",
                                headers=headers,
                                params={"app": app_name.upper()},
                                timeout=30.0
                            )
                        
                        if auth_response.status_code == 200:
                            auth_configs = auth_response.json()
                            logger.info(f"Auth configs response: {json.dumps(auth_configs, indent=2)[:500]}")
                            
                            # Look for an auth config we can use
                            if isinstance(auth_configs, list) and len(auth_configs) > 0:
                                auth_config_id = auth_configs[0].get("id")
                                logger.info(f"Using existing auth config: {auth_config_id}")
                            elif isinstance(auth_configs, dict):
                                items = auth_configs.get("items", auth_configs.get("data", []))
                                if items and len(items) > 0:
                                    auth_config_id = items[0].get("id")
                                    logger.info(f"Using existing auth config: {auth_config_id}")
                        
                        # If still no auth config, try creating one
                        if not auth_config_id:
                            logger.info(f"Creating new auth config for {app_name}")
                            create_response = await client.post(
                                "https://backend.composio.dev/api/v1/auth-configs",
                                headers=headers,
                                json={
                                    "app": app_name.upper(),
                                    "useComposioAuth": True  # Use Composio's managed auth
                                },
                                timeout=30.0
                            )
                            
                            if create_response.status_code in [200, 201]:
                                auth_config = create_response.json()
                                auth_config_id = auth_config.get("id")
                                logger.info(f"Created auth config: {auth_config_id}")
                            else:
                                logger.error(f"Failed to create auth config: {create_response.status_code} - {create_response.text[:200]}")
                except Exception as e:
                    logger.error(f"Error getting/creating auth config: {e}")
                
                if not auth_config_id:
                    logger.error(f"No auth config found for {app_name}. User needs to connect the app first.")
                    return None
            
            # Create MCP server with the connected app
            # Name must be 4-30 chars, only letters, numbers, spaces, and hyphens (no underscores)
            safe_name = f"{app_name}-mcp-{user_id[:8]}".replace("_", "-")
            
            # Create MCP server with full configuration
            # Based on Composio's API documentation, we need to specify tools explicitly
            
            # Define all Gmail tools we want to enable
            gmail_tools = [
                "GMAIL_SEND_EMAIL",
                "GMAIL_LIST_EMAILS", 
                "GMAIL_GET_EMAIL",
                "GMAIL_REPLY_TO_EMAIL",
                "GMAIL_CREATE_DRAFT",
                "GMAIL_DELETE_EMAIL",
                "GMAIL_MARK_EMAIL_AS_READ",
                "GMAIL_MARK_EMAIL_AS_UNREAD",
                "GMAIL_FORWARD_EMAIL",
                "GMAIL_GET_PROFILE",
                "GMAIL_SEARCH_EMAILS",
                "GMAIL_ADD_LABEL_TO_EMAIL",
                "GMAIL_REMOVE_LABEL_FROM_EMAIL",
                "GMAIL_CREATE_LABEL",
                "GMAIL_LIST_LABELS",
                "GMAIL_DELETE_LABEL",
                "GMAIL_TRASH_EMAIL",
                "GMAIL_UNTRASH_EMAIL",
                "GMAIL_GET_THREAD",
                "GMAIL_LIST_THREADS"
            ]
            
            # Get the connection_id for this user and app
            connection_id = None
            connections = await self.get_user_connections(user_id)
            for conn in connections:
                if conn.get("app", "").lower() == app_name.lower():
                    connection_id = conn.get("connection_id") or conn.get("id")
                    logger.info(f"Found connection_id: {connection_id}")
                    break
            
            # Build the request data - try different formats
            # Format 1: Simple with auth_config_ids and allowedTools
            data = {
                "name": safe_name,  # Name with only allowed characters
                "auth_config_ids": [auth_config_id],  # Required: auth config from OAuth connection
                "apps": [app_name.upper()],  # Apps should be uppercase (GMAIL, SLACK, etc)
            }
            
            # Add connection_id if we have it
            if connection_id:
                data["connection_ids"] = [connection_id]
                logger.info(f"Including connection_id: {connection_id}")
            
            # Add allowedTools if this is Gmail
            if app_name.lower() == "gmail":
                data["allowedTools"] = gmail_tools
                logger.info(f"Specifying {len(gmail_tools)} Gmail tools for MCP server")
            
            # Alternative format based on JS SDK example: serverConfig array
            data_alt = {
                "name": safe_name,
                "serverConfig": [
                    {
                        "authConfigId": auth_config_id,
                        "connectionId": connection_id,  # Include connection ID
                        "allowedTools": gmail_tools if app_name.lower() == "gmail" else []
                    }
                ],
                "options": {
                    "isChatAuth": False  # We already have auth from OAuth
                }
            }
            
            # Add entity_id to link the server to the user
            if user_id:
                data["entity_id"] = user_id
            
            logger.info(f"MCP server creation request (format 1): {json.dumps(data)}")
            logger.info(f"MCP server creation request (format 2): {json.dumps(data_alt)}")
            
            async with httpx.AsyncClient() as client:
                # Try the alternative format first (based on JS SDK)
                logger.info("Trying alternative format with serverConfig")
                response = await client.post(
                    "https://backend.composio.dev/api/v1/mcp/servers",
                    headers=headers,
                    json=data_alt,
                    timeout=30.0
                )
                
                # If alternative format fails, try custom endpoint
                if response.status_code not in [200, 201]:
                    logger.info(f"Alternative format failed with {response.status_code}, trying custom endpoint")
                    response = await client.post(
                        "https://backend.composio.dev/api/v1/mcp/servers/custom",
                        headers=headers,
                        json=data,
                        timeout=30.0
                    )
                
                # If custom endpoint fails, try standard endpoint
                if response.status_code == 404:
                    logger.info("Custom endpoint not found, trying standard endpoint")
                    # For standard endpoint, include allowedTools
                    standard_data = {
                        "name": data["name"],
                        "auth_config_ids": data["auth_config_ids"],
                        "apps": data["apps"]
                    }
                    if "allowedTools" in data:
                        standard_data["allowedTools"] = data["allowedTools"]
                    
                    response = await client.post(
                        "https://backend.composio.dev/api/v1/mcp/servers",
                        headers=headers,
                        json=standard_data,
                        timeout=30.0
                    )
                
                # If v1 fails, try v3 endpoint
                if response.status_code == 404:
                    logger.info("v1 endpoint not found, trying v3 endpoint")
                    response = await client.post(
                        "https://backend.composio.dev/api/v3/mcp/servers",
                        headers=headers,
                        json=data,
                        timeout=30.0
                    )
                
                if response.status_code == 200 or response.status_code == 201:
                    result = response.json()
                    logger.info(f"MCP server creation response: {json.dumps(result, indent=2)[:500]}")
                    server_id = result.get("id") or result.get("server_id") or result.get("serverId")
                    
                    # After creating the server, we might need to create an instance
                    # Check if we need to create an instance for the server to work
                    if server_id and "instance_id" not in result:
                        logger.info(f"Creating instance for MCP server {server_id}")
                        instance_response = await client.post(
                            f"https://backend.composio.dev/api/v1/mcp/servers/{server_id}/instances",
                            headers=headers,
                            json={
                                "entity_id": user_id,
                                "enable_all_tools": True
                            },
                            timeout=30.0
                        )
                        
                        if instance_response.status_code in [200, 201]:
                            instance_result = instance_response.json()
                            logger.info(f"Created instance: {json.dumps(instance_result, indent=2)[:300]}")
                            # Update result with instance info
                            if "mcp_url" in instance_result:
                                result["mcp_url"] = instance_result["mcp_url"]
                        else:
                            logger.warning(f"Failed to create instance: {instance_response.status_code}")
                    
                    # Check if Composio already returned the proper MCP URL
                    if "mcp_url" in result:
                        logger.info(f"Using Composio-provided MCP URL for {app_name}")
                        return {
                            "server_id": server_id,
                            "url": result["mcp_url"]  # Use the URL Composio provides
                        }
                    elif server_id:
                        # Construct the proper MCP URL with /mcp path and user_id parameter
                        # According to Composio docs, the format should be:
                        # https://mcp.composio.dev/composio/server/<UUID>/mcp?user_id=<user>
                        mcp_url = f"https://mcp.composio.dev/composio/server/{server_id}/mcp?user_id={user_id}"
                        logger.info(f"Created MCP server {server_id} for {app_name} with user {user_id}")
                        return {
                            "server_id": server_id,
                            "url": mcp_url
                        }
                    else:
                        logger.error(f"No server ID in response: {result}")
                        return None
                else:
                    error_text = response.text[:500] if response.text else "No error message"
                    logger.error(f"Failed to create MCP server: {response.status_code} - {error_text}")
                    
                    # If it's a 404, the API endpoint might be different
                    if response.status_code == 404:
                        logger.info("Trying alternative endpoint...")
                        # Try the generate endpoint instead
                        response2 = await client.post(
                            "https://backend.composio.dev/api/v1/mcp/servers/generate",
                            headers=headers,
                            json=data,
                            timeout=30.0
                        )
                        if response2.status_code in [200, 201]:
                            result2 = response2.json()
                            # Check if we got the mcp_url directly
                            if "mcp_url" in result2:
                                # Extract server ID from URL if present
                                import re
                                match = re.search(r'/server/([a-f0-9-]+)', result2["mcp_url"])
                                server_id = match.group(1) if match else result2.get("server_id", "unknown")
                                return {
                                    "server_id": server_id,
                                    "url": result2["mcp_url"]  # Use the provided MCP URL
                                }
                            elif "url" in result2:
                                # If we only got a base URL, construct the proper MCP URL
                                import re
                                match = re.search(r'/server/([a-f0-9-]+)', result2["url"])
                                if match:
                                    server_id = match.group(1)
                                    # Add /mcp path and user_id parameter
                                    mcp_url = f"{result2['url']}/mcp?user_id={user_id}"
                                    return {
                                        "server_id": server_id,
                                        "url": mcp_url
                                    }
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to create MCP server: {e}")
            return None
    
    def get_mcp_url_for_app(self, user_id: str, app_name: str) -> str:
        """
        Generate MCP-compatible URL for a Composio app
        
        This creates a URL that can be used with the MCP client to connect
        to Composio services.
        
        Args:
            user_id: User identifier (used as entity ID)
            app_name: Name of the app
        
        Returns:
            MCP-compatible URL
        """
        # This is a fallback - we should really create a proper MCP server
        # Just return a placeholder that won't work
        logger.error(f"Fallback URL requested for {app_name} - MCP server creation failed")
        return f"https://mcp.composio.dev/error/no-server-created"
    
    async def disconnect_app(self, user_id: str, app_name: str) -> bool:
        """
        Disconnect an app for a user
        
        Args:
            user_id: User identifier
            app_name: App name to disconnect
        
        Returns:
            Success status
        """
        if not self.is_configured():
            return False
        
        try:
            # Get user's connections
            connections = await self.get_user_connections(user_id)
            connection_id = None
            
            for conn in connections:
                if conn.get("app", "").lower() == app_name.lower():
                    connection_id = conn.get("connection_id") or conn.get("id")
                    break
            
            if connection_id:
                entity = self.client.get_entity(id=user_id)
                # Use the SDK to disconnect
                entity.get_connection(connection_id).delete()
                logger.info(f"Disconnected {app_name} (connection: {connection_id}) for user {user_id}")
                return True
            else:
                logger.warning(f"No connection found for {app_name}")
                return False
        except Exception as e:
            logger.error(f"Failed to disconnect app: {e}")
            return False