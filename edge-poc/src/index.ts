/**
 * Edge MCP Runtime - Main Worker
 * Handles routing and authentication
 */

export interface Env {
  MCP_RUNTIME: DurableObjectNamespace;
  MCP_KV: KVNamespace;
  API_KEYS: KVNamespace;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    
    // CORS headers for browser access
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };
    
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }
    
    // Extract user ID from path or auth header
    const userId = await getUserId(request, env);
    if (!userId) {
      return new Response('Unauthorized', { status: 401, headers: corsHeaders });
    }
    
    // Route to user's Durable Object
    const id = env.MCP_RUNTIME.idFromName(userId);
    const runtime = env.MCP_RUNTIME.get(id);
    
    // Handle WebSocket upgrade
    if (url.pathname.startsWith('/ws/')) {
      const upgradeHeader = request.headers.get('Upgrade');
      if (!upgradeHeader || upgradeHeader !== 'websocket') {
        return new Response('Expected Upgrade: websocket', { status: 426 });
      }
      
      return runtime.fetch(request);
    }
    
    // Regular HTTP requests
    const response = await runtime.fetch(request);
    
    // Add CORS headers to response
    const newHeaders = new Headers(response.headers);
    Object.entries(corsHeaders).forEach(([key, value]) => {
      newHeaders.set(key, value);
    });
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    });
  },
};

async function getUserId(request: Request, env: Env): Promise<string | null> {
  // Check Authorization header
  const authHeader = request.headers.get('Authorization');
  if (authHeader?.startsWith('Bearer ')) {
    const token = authHeader.substring(7);
    const userId = await env.API_KEYS.get(token);
    if (userId) return userId;
  }
  
  // Extract from URL path (for testing)
  const url = new URL(request.url);
  const match = url.pathname.match(/\/users\/([^\/]+)/);
  if (match) return match[1];
  
  return null;
}

// Durable Object export
export { MCPRuntime } from './mcp-runtime';