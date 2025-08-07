# MCP Test Client

A lightweight web-based chat interface for testing MCP (Model Context Protocol) servers using Claude. Built with React, FastAPI, and integrates with mcpd for server management.

## Features

- 💬 Chat with Claude (Anthropic's AI assistant)
- 🔧 Claude can discover and use tools from MCP servers
- 🚀 Real-time tool execution with transparent logging
- 📦 Integrates with mcpd for MCP server management
- ⚡ WebSocket-based real-time communication
- 🎨 Clean, modern UI with server selection sidebar

## Architecture

```
┌─────────────────┐
│  React Frontend │ 
│   (TypeScript)  │
└────────┬────────┘
         │ WebSocket/HTTP
┌────────▼────────┐
│  FastAPI Backend│
│    (Python)     │
│  - Anthropic SDK│
│  - mcpd client  │
└────────┬────────┘
         │ HTTP
┌────────▼────────┐
│      mcpd       │
│   (localhost)   │
└─────────────────┘
```

## Prerequisites

- Node.js 18+
- Python 3.10+
- mcpd installed and running ([mozilla-ai/mcpd](https://github.com/mozilla-ai/mcpd))
- Anthropic API key

## Setup

### 1. Install and Start mcpd

Follow the mcpd installation instructions from their repository. Start the daemon:

```bash
mcpd daemon --dev
```

This will run mcpd on `http://localhost:8090`

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run the backend
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

The app will be available at `http://localhost:5173`

## Usage

1. **Start mcpd** with your configured MCP servers
2. **Launch the backend** (FastAPI on port 8000)
3. **Launch the frontend** (React on port 5173)
4. **Select MCP servers** from the sidebar to enable their tools
5. **Chat with Claude** - it will automatically use available tools when appropriate

## Configuration

### Backend (.env)

```env
ANTHROPIC_API_KEY=your_api_key_here
MCPD_BASE_URL=http://localhost:8090/api/v1  # Default mcpd URL
```

### mcpd Configuration

Create a `.mcpd.toml` file to configure your MCP servers. Example:

```toml
[servers.weather]
command = "python"
args = ["-m", "mcp_server_weather"]

[servers.filesystem]
command = "npx"
args = ["@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"]
```

## API Endpoints

### Backend API

- `GET /servers` - List available MCP servers
- `GET /servers/{name}/tools` - Get tools for a specific server
- `POST /servers/{name}/tools/{tool}` - Execute a tool
- `WS /ws/chat` - WebSocket endpoint for chat

### mcpd API (port 8090)

- `GET /api/v1/servers` - List servers
- `GET /api/v1/servers/{name}/tools` - List server tools
- `POST /api/v1/servers/{server}/tools/{tool}` - Call tool
- `GET /api/v1/health/servers` - Health check

## Development

### Project Structure

```
mcp-client-proto/
├── backend/
│   ├── app/
│   │   └── main.py       # FastAPI application
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── App.tsx       # Main React component
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
└── mcpd/                 # mcpd source (for reference)
```

## Troubleshooting

### mcpd not connecting
- Ensure mcpd is running on port 8090
- Check mcpd logs for any errors
- Verify your `.mcpd.toml` configuration

### Claude not responding
- Verify your Anthropic API key in `.env`
- Check backend logs for API errors
- Ensure you have API credits

### Tools not appearing
- Check that MCP servers are properly configured in mcpd
- Verify server health using mcpd's health endpoints
- Look for errors in browser console

## License

MIT