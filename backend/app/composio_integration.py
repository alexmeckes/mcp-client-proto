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
            
            # Optionally get or create an auth config for this app
            # This helps Composio know which OAuth configuration to use
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
            
            
            return {
                "redirect_url": connection_request.redirectUrl,
                "connection_id": connection_request.connectedAccountId if hasattr(connection_request, 'connectedAccountId') else None,
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
                result.append({
                    "app": conn.appName if hasattr(conn, 'appName') else None,
                    "status": conn.status if hasattr(conn, 'status') else None,
                    "connected_at": conn.createdAt if hasattr(conn, 'createdAt') else None,
                    "connection_id": conn.id if hasattr(conn, 'id') else None
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
    
    async def create_mcp_server(self, user_id: str, app_name: str) -> Optional[Dict[str, str]]:
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
            
            logger.info(f"Creating MCP server for {app_name} with entity {user_id}")
            
            # Create MCP server with the connected app
            # Name must be 4-30 chars, only letters, numbers, spaces, and hyphens (no underscores)
            # Add timestamp to ensure unique name and avoid cached/broken servers
            import time
            timestamp = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
            safe_name = f"{app_name}-{timestamp}-{user_id[:6]}".replace("_", "-")
            
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
            
            # Build the request data using the correct v3 API format
            # Use toolkits + connection_ids (not apps + authConfigId)
            data = {
                "name": safe_name,  # Name with only allowed characters
                "toolkits": [app_name.upper()],  # Use toolkits array format
                "entity_id": user_id,  # Link to user
            }
            
            # Add connection_id if we have it - required for tools to work
            if connection_id:
                data["connection_ids"] = [connection_id]
                logger.info(f"Including connection_id: {connection_id} for tools access")
            else:
                logger.warning(f"No connection_id found - MCP server will have limited functionality")
            
            logger.info(f"MCP server creation request: {json.dumps(data, indent=2)}")
            
            async with httpx.AsyncClient() as client:
                # Use the correct v3 custom endpoint as recommended
                logger.info("Creating MCP server using v3/mcp/servers/custom endpoint")
                response = await client.post(
                    "https://backend.composio.dev/api/v3/mcp/servers/custom",
                    headers=headers,  # Already contains X-API-Key
                    json=data,
                    timeout=30.0
                )
                
                # Check response status
                logger.info(f"MCP server creation response status: {response.status_code}")
                
                if response.status_code == 403:
                    # Server already exists, try to get the existing one
                    error_response = response.json()
                    if "already exists" in error_response.get("error", {}).get("message", ""):
                        logger.info("MCP server already exists, attempting to retrieve existing server")
                        try:
                            # Try to list existing servers and find the one with this name
                            list_response = await client.get(
                                "https://backend.composio.dev/api/v3/mcp/servers",
                                headers=headers,
                                timeout=30.0
                            )
                            if list_response.status_code == 200:
                                servers = list_response.json()
                                servers_list = servers if isinstance(servers, list) else servers.get("items", servers.get("data", []))
                                for server in servers_list:
                                    if server.get("name") == safe_name:
                                        server_id = server.get("id") or server.get("serverId")
                                        if server_id:
                                            logger.info(f"Found existing MCP server: {server_id}")
                                            mcp_url = f"https://mcp.composio.dev/composio/server/{server_id}/mcp?user_id={user_id}"
                                            return {
                                                "server_id": server_id,
                                                "url": mcp_url
                                            }
                        except Exception as e:
                            logger.error(f"Failed to retrieve existing server: {e}")
                
                if response.status_code == 200 or response.status_code == 201:
                    result = response.json()
                    logger.info(f"MCP server creation response: {json.dumps(result, indent=2)[:500]}")
                    server_id = result.get("id") or result.get("server_id") or result.get("serverId")
                    
                    # After creating the server, we might need to create an instance
                    # Use the correct v3 instance endpoint
                    if server_id and "instance_id" not in result:
                        logger.info(f"Creating instance for MCP server {server_id}")
                        instance_response = await client.post(
                            f"https://backend.composio.dev/api/v3/mcp/servers/{server_id}/instances",
                            headers=headers,  # Already contains X-API-Key  
                            json={
                                "user_id": user_id
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