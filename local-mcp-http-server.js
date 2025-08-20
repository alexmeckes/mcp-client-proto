#!/usr/bin/env node

/**
 * HTTP Gateway for MCP Servers
 * This wraps any stdio-based MCP server and exposes it via HTTP
 * 
 * Usage: node local-mcp-http-server.js [mcp-server-command] [port]
 * Example: node local-mcp-http-server.js "npx @modelcontextprotocol/server-filesystem" 3000
 */

const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');

const app = express();
const PORT = process.argv[3] || 3000;
const MCP_COMMAND = process.argv[2] || 'npx @modelcontextprotocol/server-filesystem';

// Enable CORS for all origins (adjust for production)
app.use(cors());
app.use(express.json());
app.use(express.text({ type: 'text/event-stream' }));

let mcpProcess = null;
let requestId = 1;
const pendingRequests = new Map();

// Start the MCP server process
function startMCPServer() {
  console.log(`Starting MCP server: ${MCP_COMMAND}`);
  
  const [command, ...args] = MCP_COMMAND.split(' ');
  mcpProcess = spawn(command, args, {
    stdio: ['pipe', 'pipe', 'pipe']
  });

  mcpProcess.stdout.on('data', (data) => {
    try {
      const response = JSON.parse(data.toString());
      if (response.id && pendingRequests.has(response.id)) {
        const { resolve } = pendingRequests.get(response.id);
        pendingRequests.delete(response.id);
        resolve(response);
      }
    } catch (e) {
      console.error('Failed to parse MCP response:', e);
    }
  });

  mcpProcess.stderr.on('data', (data) => {
    console.error('MCP stderr:', data.toString());
  });

  mcpProcess.on('close', (code) => {
    console.log(`MCP process exited with code ${code}`);
    // Restart if needed
    setTimeout(startMCPServer, 1000);
  });
}

// Send request to MCP server
function sendToMCP(request) {
  return new Promise((resolve, reject) => {
    const id = request.id || requestId++;
    const fullRequest = { ...request, id };
    
    pendingRequests.set(id, { resolve, reject });
    
    mcpProcess.stdin.write(JSON.stringify(fullRequest) + '\n');
    
    // Timeout after 30 seconds
    setTimeout(() => {
      if (pendingRequests.has(id)) {
        pendingRequests.delete(id);
        reject(new Error('Request timeout'));
      }
    }, 30000);
  });
}

// Main MCP endpoint
app.post('/', async (req, res) => {
  try {
    console.log('Received request:', req.body);
    
    // Handle SSE response for initialize and tools/list
    if (req.headers.accept?.includes('text/event-stream')) {
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      
      const response = await sendToMCP(req.body);
      
      // Send as SSE
      res.write('event: message\n');
      res.write(`data: ${JSON.stringify(response)}\n\n`);
      res.end();
    } else {
      // Regular JSON response
      const response = await sendToMCP(req.body);
      res.json(response);
    }
  } catch (error) {
    console.error('Error handling request:', error);
    res.status(500).json({
      jsonrpc: '2.0',
      error: {
        code: -32603,
        message: error.message
      },
      id: req.body.id
    });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    mcp_server: MCP_COMMAND,
    port: PORT 
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`HTTP MCP Gateway running on http://localhost:${PORT}`);
  console.log(`MCP Server: ${MCP_COMMAND}`);
  startMCPServer();
});

// Graceful shutdown
process.on('SIGINT', () => {
  if (mcpProcess) {
    mcpProcess.kill();
  }
  process.exit(0);
});