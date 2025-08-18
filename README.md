# MCP Client Prototype

A multi-model chat interface with Model Context Protocol (MCP) support for tool calling. Supports remote MCP servers like Composio for integrations.

## Features

- 🤖 **Multi-Model Support**: Works with Claude, GPT-4, and other models via any-llm library
- 🔧 **Remote MCP Servers**: Connect to remote MCP servers like Composio for tool integrations
- 🌐 **Tool Calling**: Execute tools from connected MCP servers during conversations
- 💬 **Real-time Streaming**: WebSocket-based streaming for responsive chat
- 🔑 **API Key Management**: Secure client-side API key storage

## Architecture

- **Frontend**: React + TypeScript with Vite
- **Backend**: FastAPI (Python) with WebSocket support
- **MCP Integration**: Remote MCP servers via HTTP/SSE protocol
- **Deployment**: Docker container deployable to Railway/Vercel

## Quick Start

### Local Development

1. **Backend Setup**:
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

2. **Frontend Setup**:
```bash
cd frontend
npm install
npm run dev
```

3. **Add Remote MCP Servers**:
   - Use the "Quick Add" input to add remote MCP server URLs
   - Example: `https://mcp.composio.dev/github/mcp?customerId=YOUR_ID`

## Remote MCP Servers

This client supports any MCP-compatible remote server. Popular options include:

- **Composio**: Provides integrations for GitHub, Supabase, and more
  - Format: `https://mcp.composio.dev/{service}/mcp?customerId={your_id}`
- **Custom Servers**: Any HTTP/HTTPS endpoint implementing the MCP protocol

## Deployment

### Railway (Backend)

```bash
railway up
```

The Dockerfile is configured to run the Python backend with remote MCP support.

### Vercel (Frontend)

```bash
cd frontend
vercel
```

## Environment Variables

### Backend
- `PORT`: Server port (default: 8000)
- `FRONTEND_URL`: Frontend URL for CORS
- `CLOUD_MODE`: Set to `true` in production

### Frontend
- `VITE_API_URL`: Backend API URL
- `VITE_WS_URL`: Backend WebSocket URL

## Security Notes

- API keys are stored client-side in localStorage
- Remote MCP servers handle their own authentication
- No MCPD daemon required - all MCP servers are remote

## Why No MCPD?

MCPD (MCP Daemon) was originally included but has been removed because:
- It's designed for single-user local development, not multi-user web apps
- No user isolation or multi-tenancy support
- Security concerns with shared server processes
- Remote MCP servers (like Composio) provide better isolation and scaling

For local development with MCP servers, consider running them separately and exposing them as HTTP endpoints.

## Contributing

Pull requests welcome! Please ensure:
- Code follows existing patterns
- Tests pass (when available)
- Documentation is updated

## License

MIT