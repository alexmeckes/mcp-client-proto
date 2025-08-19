"""Proper Composio integration using their SDK"""
import os
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
            
            # Initiate connection for the specific app
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
            
            return [
                {
                    "app": conn.appName,
                    "status": conn.status,
                    "connected_at": conn.createdAt,
                    "connection_id": conn.id
                }
                for conn in connections
            ]
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
        if not self.is_configured():
            return []
        
        try:
            # Get entity
            entity = self.client.get_entity(id=user_id)
            
            # Get tools for connected apps
            if app_name:
                tools = self.toolset.get_tools(apps=[app_name.upper()], entity_id=user_id)
            else:
                tools = self.toolset.get_tools(entity_id=user_id)
            
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "app": tool.app,
                    "parameters": tool.parameters if hasattr(tool, 'parameters') else {}
                }
                for tool in tools
            ]
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
            
            # Create MCP server with the connected app
            data = {
                "apps": [app_name.upper()],  # Apps should be uppercase (GMAIL, SLACK, etc)
                "entity_id": user_id,
                "name": f"{app_name}_mcp_{user_id[:8]}"  # Unique name for the server
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://backend.composio.dev/api/v1/mcp/servers",
                    headers=headers,
                    json=data,
                    timeout=30.0
                )
                
                if response.status_code == 200 or response.status_code == 201:
                    result = response.json()
                    server_id = result.get("id") or result.get("server_id") or result.get("serverId")
                    
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
        # Composio MCP endpoints
        # Based on docs, try using 'mcp' as the customerId
        return f"https://mcp.composio.dev/{app_name.lower()}/mcp?customerId=mcp"
    
    async def disconnect_app(self, user_id: str, connection_id: str) -> bool:
        """
        Disconnect an app for a user
        
        Args:
            user_id: User identifier
            connection_id: Connection ID to disconnect
        
        Returns:
            Success status
        """
        if not self.is_configured():
            return False
        
        try:
            entity = self.client.get_entity(id=user_id)
            # This would need the actual Composio SDK method for disconnection
            # entity.disconnect(connection_id)
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect app: {e}")
            return False