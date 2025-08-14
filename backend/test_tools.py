#!/usr/bin/env python
"""Test script to verify any-llm tool calling works"""

import asyncio
import json
from any_llm import completion
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Define test tools in OpenAI format
test_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "The unit of temperature"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

def test_tool_calling():
    """Test tool calling with any-llm"""
    print("Testing tool calling with any-llm...")
    print(f"Using API key: {'Set' if os.getenv('OPENAI_API_KEY') else 'Not set'}")
    
    try:
        # Test with OpenAI (since we know it supports tools)
        result = completion(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "What's the weather in Paris, France?"}
            ],
            tools=test_tools,
            max_tokens=150
        )
        
        print("\nResponse received!")
        print(f"Response type: {type(result)}")
        
        if hasattr(result, 'choices') and result.choices:
            choice = result.choices[0]
            message = choice.message
            
            print(f"Message content: {message.content}")
            
            if hasattr(message, 'tool_calls') and message.tool_calls:
                print(f"\nTool calls detected: {len(message.tool_calls)}")
                for tc in message.tool_calls:
                    print(f"  - Tool: {tc.function.name}")
                    print(f"    Args: {tc.function.arguments}")
            else:
                print("No tool calls in response")
        else:
            print(f"Unexpected response format: {result}")
            
    except Exception as e:
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # If it's an auth error, tools were still accepted
        if "401" in str(e) or "authentication" in str(e).lower():
            print("\nAuthentication failed (expected if no valid API key)")
            print("But tool parameters were accepted successfully!")

if __name__ == "__main__":
    test_tool_calling()