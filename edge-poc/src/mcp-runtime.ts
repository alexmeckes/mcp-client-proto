/**
 * MCP Runtime Durable Object
 * Manages MCP servers for a single user
 */

import { MCPServer } from './types';
import { FilesystemServer } from './servers/filesystem';
import { MemoryServer } from './servers/memory';
import { TimeServer } from './servers/time';

export class MCPRuntime {
  private state: DurableObjectState;
  private storage: DurableObjectStorage;
  private servers: Map<string, MCPServer>;
  private websockets: Set<WebSocket>;
  private env: any;

  constructor(state: DurableObjectState, env: any) {
    this.state = state;
    this.storage = state.storage;
    this.env = env;
    this.servers = new Map();
    this.websockets = new Set();
    
    // Initialize built-in servers
    this.initializeBuiltinServers();
  }
  
  private async initializeBuiltinServers() {
    // These are always available
    this.servers.set('time', new TimeServer());
    
    // Load user-installed servers from storage
    const installedServers = await this.storage.get<string[]>('installed-servers') || [];
    for (const serverName of installedServers) {
      await this.loadServer(serverName);
    }
  }
  
  private async loadServer(name: string) {
    const config = await this.storage.get(`server-config:${name}`);
    
    switch (name) {
      case 'filesystem':
        this.servers.set(name, new FilesystemServer(this.storage));
        break;
      case 'memory':
        this.servers.set(name, new MemoryServer(this.storage));
        break;
      // Add more servers as needed
    }
  }
  
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    
    // Handle WebSocket connections
    if (path.startsWith('/ws/')) {
      return this.handleWebSocket(request);
    }
    
    // Parse API path: /api/v1/users/{userId}/...
    const pathParts = path.split('/').filter(Boolean);
    
    try {
      // List servers
      if (path.endsWith('/servers') && request.method === 'GET') {
        return this.handleListServers();
      }
      
      // Install server
      if (path.endsWith('/servers') && request.method === 'POST') {
        const body = await request.json() as { name: string; config?: any };
        return this.handleInstallServer(body.name, body.config);
      }
      
      // Uninstall server
      if (path.match(/\/servers\/([^\/]+)$/) && request.method === 'DELETE') {
        const serverName = pathParts[pathParts.length - 1];
        return this.handleUninstallServer(serverName);
      }
      
      // Get server tools
      if (path.match(/\/servers\/([^\/]+)\/tools$/) && request.method === 'GET') {
        const serverName = pathParts[pathParts.length - 2];
        return this.handleGetTools(serverName);
      }
      
      // Call tool
      if (path.match(/\/servers\/([^\/]+)\/tools\/([^\/]+)$/) && request.method === 'POST') {
        const serverName = pathParts[pathParts.length - 3];
        const toolName = pathParts[pathParts.length - 1];
        const body = await request.json();
        return this.handleCallTool(serverName, toolName, body.params || {});
      }
      
      return new Response('Not Found', { status: 404 });
    } catch (error: any) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }
  
  private async handleWebSocket(request: Request): Promise<Response> {
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    
    this.state.acceptWebSocket(server);
    this.websockets.add(server);
    
    server.addEventListener('message', async (event) => {
      try {
        const message = JSON.parse(event.data as string);
        await this.handleWebSocketMessage(server, message);
      } catch (error: any) {
        server.send(JSON.stringify({
          type: 'error',
          error: error.message,
        }));
      }
    });
    
    server.addEventListener('close', () => {
      this.websockets.delete(server);
    });
    
    // Send initial state
    server.send(JSON.stringify({
      type: 'connected',
      servers: Array.from(this.servers.keys()),
    }));
    
    return new Response(null, {
      status: 101,
      webSocket: client,
    });
  }
  
  private async handleWebSocketMessage(ws: WebSocket, message: any) {
    switch (message.type) {
      case 'call_tool':
        const result = await this.callTool(
          message.server,
          message.tool,
          message.params
        );
        ws.send(JSON.stringify({
          type: 'tool_result',
          id: message.id,
          result,
        }));
        break;
        
      case 'list_tools':
        const tools = await this.getTools(message.server);
        ws.send(JSON.stringify({
          type: 'tools_list',
          id: message.id,
          tools,
        }));
        break;
    }
  }
  
  private async handleListServers(): Promise<Response> {
    const servers = Array.from(this.servers.entries()).map(([name, server]) => ({
      name,
      description: server.description,
      installed: true,
    }));
    
    return Response.json(servers);
  }
  
  private async handleInstallServer(name: string, config?: any): Promise<Response> {
    if (this.servers.has(name)) {
      return Response.json({ message: 'Server already installed' });
    }
    
    // Store configuration
    await this.storage.put(`server-config:${name}`, config || {});
    
    // Update installed servers list
    const installed = await this.storage.get<string[]>('installed-servers') || [];
    if (!installed.includes(name)) {
      installed.push(name);
      await this.storage.put('installed-servers', installed);
    }
    
    // Load the server
    await this.loadServer(name);
    
    // Notify WebSocket clients
    this.broadcast({
      type: 'server_installed',
      server: name,
    });
    
    return Response.json({ message: `Server ${name} installed` });
  }
  
  private async handleUninstallServer(name: string): Promise<Response> {
    if (!this.servers.has(name)) {
      return new Response('Server not found', { status: 404 });
    }
    
    // Remove from memory
    const server = this.servers.get(name);
    if (server?.cleanup) {
      await server.cleanup();
    }
    this.servers.delete(name);
    
    // Remove from storage
    await this.storage.delete(`server-config:${name}`);
    const installed = await this.storage.get<string[]>('installed-servers') || [];
    const index = installed.indexOf(name);
    if (index > -1) {
      installed.splice(index, 1);
      await this.storage.put('installed-servers', installed);
    }
    
    // Notify WebSocket clients
    this.broadcast({
      type: 'server_uninstalled',
      server: name,
    });
    
    return Response.json({ message: `Server ${name} uninstalled` });
  }
  
  private async handleGetTools(serverName: string): Promise<Response> {
    const tools = await this.getTools(serverName);
    return Response.json(tools);
  }
  
  private async handleCallTool(
    serverName: string,
    toolName: string,
    params: any
  ): Promise<Response> {
    const result = await this.callTool(serverName, toolName, params);
    return Response.json(result);
  }
  
  private async getTools(serverName: string): Promise<any[]> {
    const server = this.servers.get(serverName);
    if (!server) {
      throw new Error(`Server ${serverName} not found`);
    }
    
    return server.getTools();
  }
  
  private async callTool(
    serverName: string,
    toolName: string,
    params: any
  ): Promise<any> {
    const server = this.servers.get(serverName);
    if (!server) {
      throw new Error(`Server ${serverName} not found`);
    }
    
    const tool = server.getTools().find(t => t.name === toolName);
    if (!tool) {
      throw new Error(`Tool ${toolName} not found in server ${serverName}`);
    }
    
    return server.callTool(toolName, params);
  }
  
  private broadcast(message: any) {
    const data = JSON.stringify(message);
    for (const ws of this.websockets) {
      try {
        ws.send(data);
      } catch (error) {
        // WebSocket might be closed
        this.websockets.delete(ws);
      }
    }
  }
}