"""Composio OAuth authentication handler"""
import os
import secrets
from typing import Optional
from urllib.parse import urlencode
import httpx

# Composio OAuth endpoints (these would need to be confirmed with Composio docs)
COMPOSIO_AUTH_URL = "https://app.composio.dev/oauth/authorize"
COMPOSIO_TOKEN_URL = "https://api.composio.dev/oauth/token"
COMPOSIO_API_BASE = "https://api.composio.dev"

# OAuth configuration
CLIENT_ID = os.getenv("COMPOSIO_CLIENT_ID", "")  # Would need to register app with Composio
CLIENT_SECRET = os.getenv("COMPOSIO_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("COMPOSIO_REDIRECT_URI", "http://localhost:3000/auth/composio/callback")

class ComposioAuth:
    """Handle Composio OAuth flow"""
    
    def __init__(self):
        self.pending_states = {}  # Store state tokens temporarily
    
    def get_auth_url(self, user_id: str) -> str:
        """Generate OAuth authorization URL"""
        state = secrets.token_urlsafe(32)
        self.pending_states[state] = user_id
        
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "state": state,
            "scope": "read write tools"  # Request necessary scopes
        }
        
        # If Composio doesn't have OAuth yet, we might need to use API key flow
        # For now, return a URL that would work with standard OAuth
        return f"{COMPOSIO_AUTH_URL}?{urlencode(params)}"
    
    async def exchange_code(self, code: str, state: str) -> dict:
        """Exchange authorization code for access token"""
        
        # Verify state token
        if state not in self.pending_states:
            raise ValueError("Invalid state token")
        
        user_id = self.pending_states.pop(state)
        
        # Exchange code for token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                COMPOSIO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI
                }
            )
            
            if response.status_code != 200:
                raise ValueError(f"Failed to exchange code: {response.text}")
            
            token_data = response.json()
            
            # Get user's entity ID and available tools
            access_token = token_data.get("access_token")
            user_info = await self.get_user_info(access_token)
            
            return {
                "user_id": user_id,
                "access_token": access_token,
                "entity_id": user_info.get("entity_id", "default"),
                "available_tools": user_info.get("tools", [])
            }
    
    async def get_user_info(self, access_token: str) -> dict:
        """Get user information and available tools from Composio"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COMPOSIO_API_BASE}/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code == 200:
                return response.json()
            
            # Fallback if endpoint doesn't exist
            return {
                "entity_id": "default",
                "tools": ["github", "slack", "notion", "gmail", "calendar"]
            }
    
    async def get_tool_connections(self, access_token: str) -> list:
        """Get user's connected tools"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COMPOSIO_API_BASE}/connections",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code == 200:
                return response.json()
            
            return []