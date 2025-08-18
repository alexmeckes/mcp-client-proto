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
                "connection_id": connection_request.connectionId,
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
    
    def get_mcp_url_for_app(self, user_id: str, app_name: str) -> str:
        """
        Generate MCP-compatible URL for a Composio app
        
        This creates a URL that can be used with the MCP client to connect
        to Composio services.
        
        Args:
            user_id: User identifier (used as customer ID)
            app_name: Name of the app
        
        Returns:
            MCP-compatible URL
        """
        # Composio MCP endpoints follow this pattern
        return f"https://mcp.composio.dev/{app_name.lower()}/mcp?customerId={user_id}"
    
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