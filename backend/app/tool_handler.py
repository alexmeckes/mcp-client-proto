"""
Tool handler for proper tool-use conversation flow with Claude
"""
import json
import httpx
from typing import List, Dict, Any
try:
    from anthropic import AsyncAnthropic
except (ImportError, AttributeError) as e:
    print(f"Warning: Could not import AsyncAnthropic: {e}")
    AsyncAnthropic = None


async def execute_tool(
    tool_name: str,
    server_name: str,
    arguments: Dict[str, Any],
    remote_mcp_servers: Dict,
    MCPD_BASE_URL: str
) -> Dict[str, Any]:
    """Execute a single tool and return the result"""
    
    # Check if remote or local server
    if server_name in remote_mcp_servers:
        # Remote server execution
        config = remote_mcp_servers[server_name]
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                headers = config.headers.copy()
                
                # Check if it's Composio
                if "composio" in config.endpoint:
                    # Composio uses SSE for MCP protocol
                    headers["Accept"] = "application/json, text/event-stream"
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
                    
                    # Parse SSE response for Composio
                    text = tool_response.text
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
                        return {"error": "Failed to parse SSE response"}
                else:
                    # Standard JSON-RPC for other remotes
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
                                "arguments": arguments
                            },
                            "id": 1
                        }
                    )
                    result = tool_response.json()
                
                # Extract result based on response format
                if isinstance(result, dict):
                    if "result" in result:
                        # For Composio, the result might have content array
                        if isinstance(result["result"], dict) and "content" in result["result"]:
                            # Extract text from content array
                            content = result["result"]["content"]
                            if isinstance(content, list) and len(content) > 0:
                                if "text" in content[0]:
                                    return json.loads(content[0]["text"]) if isinstance(content[0]["text"], str) else content[0]["text"]
                                else:
                                    return content[0]
                            else:
                                return content
                        else:
                            return result["result"]
                    elif "data" in result:
                        return result["data"]
                    else:
                        return result
                else:
                    return result
                    
            except Exception as e:
                return {"error": str(e)}
    else:
        # Local server via mcpd
        async with httpx.AsyncClient() as client:
            try:
                tool_response = await client.post(
                    f"{MCPD_BASE_URL}/servers/{server_name}/tools/{tool_name}",
                    json=arguments
                )
                return tool_response.json()
            except Exception as e:
                return {"error": str(e)}


async def handle_tool_use_response(
    response,
    websocket,
    model: str,
    llm_messages: List[Dict],
    anthropic_client,  # Remove type hint since AsyncAnthropic might be None
    remote_mcp_servers: Dict,
    MCPD_BASE_URL: str
) -> None:
    """Handle a response from Claude that contains tool use"""
    
    # Check if response contains tool calls
    has_tool_calls = any(hasattr(c, 'type') and c.type == 'tool_use' for c in response.content)
    
    if not has_tool_calls:
        # No tools, just send the message
        await websocket.send_json({
            "type": "message",
            "role": "assistant",
            "content": response.content[0].text if hasattr(response.content[0], 'text') else str(response.content),
            "model": model
        })
        return
    
    # Send initial assistant message (if any text content before tools)
    initial_text = ""
    for content in response.content:
        if hasattr(content, 'text'):
            initial_text = content.text
            break
    
    if initial_text:
        await websocket.send_json({
            "type": "message",
            "role": "assistant",
            "content": initial_text,
            "model": model
        })
    
    # Collect tool use blocks for the response
    tool_use_blocks = []
    
    # Execute each tool and collect results
    for content in response.content:
        if hasattr(content, 'type') and content.type == 'tool_use':
            server_name, tool_name = content.name.split("__", 1)
            
            # Send tool call notification to frontend
            await websocket.send_json({
                "type": "tool_call",
                "server": server_name,
                "tool": tool_name,
                "arguments": content.input
            })
            
            # Execute the tool
            tool_result = await execute_tool(
                tool_name=tool_name,
                server_name=server_name,
                arguments=content.input,
                remote_mcp_servers=remote_mcp_servers,
                MCPD_BASE_URL=MCPD_BASE_URL
            )
            
            # Send tool result to frontend for display
            await websocket.send_json({
                "type": "tool_result",
                "server": server_name,
                "tool": tool_name,
                "result": tool_result
            })
            
            # Store tool use block for continuing conversation
            tool_use_blocks.append({
                "type": "tool_use",
                "id": content.id,
                "name": content.name,
                "input": content.input
            })
            
            # Store tool result for continuing conversation
            tool_use_blocks.append({
                "type": "tool_result",
                "tool_use_id": content.id,
                "content": str(tool_result) if not isinstance(tool_result, str) else tool_result
            })
    
    # Now continue the conversation with Claude including the tool results
    # Add the assistant's message with tool use to the conversation
    llm_messages.append({
        "role": "assistant",
        "content": tool_use_blocks
    })
    
    # Get Claude's final response after processing tool results
    if not anthropic_client:
        await websocket.send_json({
            "type": "error",
            "message": "Anthropic client not available to process tool results"
        })
        return
        
    try:
        model_name = model.split("/")[1] if "/" in model else model
        final_response = await anthropic_client.messages.create(
            model=model_name,
            messages=llm_messages,
            max_tokens=4096
        )
        
        # Send Claude's final interpretation of the tool results
        final_text = ""
        for content in final_response.content:
            if hasattr(content, 'text'):
                final_text += content.text
        
        if final_text:
            await websocket.send_json({
                "type": "message",
                "role": "assistant",
                "content": final_text,
                "model": model
            })
        
        # If there are more tool calls in the final response, handle them recursively
        if any(hasattr(c, 'type') and c.type == 'tool_use' for c in final_response.content):
            await handle_tool_use_response(
                final_response,
                websocket,
                model,
                llm_messages,
                anthropic_client,
                remote_mcp_servers,
                MCPD_BASE_URL
            )
            
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to get final response from Claude: {str(e)}"
        })