"""
Direct Composio tools integration without MCP
This bypasses the MCP protocol and uses Composio's API directly
"""
import os
import httpx
import logging
from typing import List, Dict, Any, Optional
from composio import Composio

logger = logging.getLogger(__name__)

class ComposioToolsDirect:
    """Direct integration with Composio tools, bypassing MCP"""
    
    def __init__(self):
        self.api_key = os.getenv("COMPOSIO_API_KEY", "")
        if self.api_key:
            self.client = Composio(api_key=self.api_key)
        else:
            self.client = None
            
    async def get_gmail_tools(self, user_id: str) -> List[Dict[str, Any]]:
        """Get Gmail tools for a user"""
        if not self.api_key:
            return []
            
        try:
            # Use Composio's action enum to get Gmail tools
            from composio.client.enums import Action, App
            
            # Get common Gmail actions
            gmail_actions = [
                "GMAIL_SEND_EMAIL",
                "GMAIL_GET_PROFILE", 
                "GMAIL_LIST_EMAILS",
                "GMAIL_GET_EMAIL",
                "GMAIL_CREATE_DRAFT",
                "GMAIL_REPLY_TO_EMAIL",
                "GMAIL_FORWARD_EMAIL",
                "GMAIL_DELETE_EMAIL",
                "GMAIL_MARK_EMAIL_AS_READ",
                "GMAIL_MARK_EMAIL_AS_UNREAD",
                "GMAIL_ADD_LABEL_TO_EMAIL",
                "GMAIL_REMOVE_LABEL_FROM_EMAIL",
                "GMAIL_LIST_LABELS",
                "GMAIL_CREATE_LABEL",
            ]
            
            tools = []
            for action_name in gmail_actions:
                tools.append({
                    "name": action_name,
                    "description": f"Gmail action: {action_name.replace('GMAIL_', '').replace('_', ' ').title()}",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                })
            
            logger.info(f"Returning {len(tools)} Gmail tools")
            return tools
            
        except Exception as e:
            logger.error(f"Failed to get Gmail tools: {e}")
            return []
    
    async def execute_gmail_tool(self, user_id: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Gmail tool"""
        if not self.client:
            return {"error": "Composio not configured"}
            
        try:
            # Get entity for user
            entity = self.client.get_entity(id=user_id)
            
            # Execute the action
            from composio.client.enums import Action
            
            # Convert tool name to action
            action = getattr(Action, tool_name, None)
            if not action:
                return {"error": f"Unknown action: {tool_name}"}
            
            # Execute through entity
            result = entity.execute(action=action, params=params)
            
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