# Edge MCP Runtime - Proof of Concept

This is a proof-of-concept implementation for running MCP servers on Cloudflare Workers with Durable Objects.

## Quick Start

```bash
# Install dependencies
npm install

# Deploy to Cloudflare
npm run deploy

# Test locally
npm run dev
```

## Architecture

The edge runtime provides:
- Stateful MCP server instances via Durable Objects
- Per-user isolation
- Persistent storage via KV
- WebSocket support for real-time communication

## Project Structure

```
edge-poc/
├── src/
│   ├── index.ts           # Main worker router
│   ├── mcp-runtime.ts     # Durable Object for MCP
│   ├── servers/           # MCP server implementations
│   │   ├── filesystem.ts  # Virtual filesystem
│   │   └── memory.ts      # In-memory data store
│   └── storage/           # Storage abstraction
│       └── kv-storage.ts  # KV-backed storage
├── wrangler.toml          # Cloudflare config
└── package.json
```

## API Endpoints

### Install Server
```http
POST /api/v1/users/{userId}/servers
Content-Type: application/json

{
  "name": "filesystem",
  "config": {}
}
```

### Call Tool
```http
POST /api/v1/users/{userId}/servers/{serverName}/tools/{toolName}
Content-Type: application/json

{
  "params": {
    "path": "/example.txt"
  }
}
```

### WebSocket Connection
```
wss://your-worker.workers.dev/ws/{userId}
```

## Supported MCP Servers

Initially supporting:
- `filesystem` - Virtual file system backed by KV
- `memory` - In-memory key-value store
- `time` - Simple time utilities

## Cost Estimate

- **Workers**: 100k requests/day free
- **Durable Objects**: $0.15/million requests
- **KV Storage**: 1GB free, then $0.50/GB
- **Estimated**: $0.10-0.50 per active user/month

## Limitations

- No native binaries
- 128MB memory limit per DO
- 1GB storage per DO
- No direct file system access
- Limited to Web APIs