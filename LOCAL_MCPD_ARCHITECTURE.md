# Local MCPD Service Architecture

## Overview
This approach separates MCPD into a **local desktop service** that users install, while the web interface can be cloud-hosted or local. This provides full MCP server capabilities without cloud infrastructure costs.

## Architecture

```
┌──────────────────────────────────┐
│   Cloud-Hosted Web UI (Vercel)    │
│   https://mcp-client.vercel.app   │
└────────────┬─────────────────────┘
             │ HTTPS/WSS
             │ (with local cert)
┌────────────▼─────────────────────┐
│   Local MCPD Service              │
│   localhost:8090                  │
│   ┌─────────────────────────┐    │
│   │ - WebSocket Server      │    │
│   │ - CORS enabled          │    │
│   │ - Local cert (mkcert)   │    │
│   └─────────────────────────┘    │
│   ┌─────────────────────────┐    │
│   │ MCP Servers:            │    │
│   │ - filesystem            │    │
│   │ - sqlite                │    │
│   │ - github                │    │
│   │ - Any npm package       │    │
│   └─────────────────────────┘    │
└──────────────────────────────────┘
             │
┌────────────▼─────────────────────┐
│   Local System Resources          │
│   - File system                   │
│   - Databases                     │
│   - Git repositories              │
│   - SSH keys                      │
└──────────────────────────────────┘
```

## Implementation Approaches

### Option 1: Electron App (Recommended)
Create an Electron app that bundles MCPD with a system tray interface.

```typescript
// electron/main.ts
import { app, BrowserWindow, Tray, Menu } from 'electron';
import { spawn } from 'child_process';
import path from 'path';

class MCPDDesktop {
  private tray: Tray;
  private mcpdProcess: any;
  private mainWindow: BrowserWindow | null = null;
  
  constructor() {
    this.setupTray();
    this.startMCPD();
    this.setupAutoLaunch();
  }
  
  private setupTray() {
    this.tray = new Tray(path.join(__dirname, 'icon.png'));
    
    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Open MCP Client',
        click: () => this.openWebUI()
      },
      {
        label: 'MCPD Status',
        enabled: false,
        id: 'status'
      },
      { type: 'separator' },
      {
        label: 'Start MCPD',
        click: () => this.startMCPD(),
        id: 'start'
      },
      {
        label: 'Stop MCPD',
        click: () => this.stopMCPD(),
        id: 'stop'
      },
      { type: 'separator' },
      {
        label: 'Settings',
        click: () => this.openSettings()
      },
      {
        label: 'Quit',
        click: () => {
          this.stopMCPD();
          app.quit();
        }
      }
    ]);
    
    this.tray.setToolTip('MCP Desktop Service');
    this.tray.setContextMenu(contextMenu);
  }
  
  private startMCPD() {
    // Start MCPD with CORS enabled for web access
    this.mcpdProcess = spawn('mcpd', [
      'daemon',
      '--port', '8090',
      '--cors-origin', 'https://mcp-client.vercel.app,http://localhost:3000',
      '--enable-https',  // Use local cert for secure connection
      '--cert-dir', app.getPath('userData')
    ], {
      cwd: app.getPath('userData'),
      env: {
        ...process.env,
        MCPD_DATA_DIR: path.join(app.getPath('userData'), 'mcpd-data')
      }
    });
    
    this.mcpdProcess.stdout.on('data', (data: Buffer) => {
      console.log('MCPD:', data.toString());
      this.updateStatus('Running on localhost:8090');
    });
    
    this.mcpdProcess.stderr.on('data', (data: Buffer) => {
      console.error('MCPD Error:', data.toString());
    });
    
    this.mcpdProcess.on('exit', (code: number) => {
      this.updateStatus(`Stopped (code ${code})`);
    });
  }
  
  private stopMCPD() {
    if (this.mcpdProcess) {
      this.mcpdProcess.kill();
      this.mcpdProcess = null;
    }
  }
  
  private openWebUI() {
    shell.openExternal('https://mcp-client.vercel.app');
  }
  
  private updateStatus(status: string) {
    const menu = this.tray.getContextMenu();
    menu.getMenuItemById('status').label = `Status: ${status}`;
    this.tray.setContextMenu(menu);
  }
}

app.whenReady().then(() => {
  new MCPDDesktop();
});
```

### Option 2: Native System Service
Install MCPD as a system service using platform-specific tools.

**macOS (launchd)**:
```xml
<!-- ~/Library/LaunchAgents/com.mcp.daemon.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mcp.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/mcpd</string>
        <string>daemon</string>
        <string>--port</string>
        <string>8090</string>
        <string>--cors-origin</string>
        <string>https://mcp-client.vercel.app</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/mcpd.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/mcpd.error.log</string>
</dict>
</plist>
```

**Windows (Service)**:
```powershell
# Install as Windows Service
New-Service -Name "MCPD" `
  -BinaryPathName "C:\Program Files\MCPD\mcpd.exe daemon --port 8090" `
  -DisplayName "MCP Daemon" `
  -Description "Model Context Protocol Daemon" `
  -StartupType Automatic

Start-Service -Name "MCPD"
```

**Linux (systemd)**:
```ini
# /etc/systemd/system/mcpd.service
[Unit]
Description=MCP Daemon
After=network.target

[Service]
Type=simple
User=%i
ExecStart=/usr/local/bin/mcpd daemon --port 8090 --cors-origin https://mcp-client.vercel.app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Option 3: Docker Desktop Integration
Package MCPD as a Docker container that runs locally.

```dockerfile
# Dockerfile.desktop
FROM node:20-alpine

RUN apk add --no-cache git openssh-client

WORKDIR /app

# Install MCPD
COPY mcpd /usr/local/bin/mcpd
RUN chmod +x /usr/local/bin/mcpd

# Install common MCP servers
RUN npm install -g \
  @modelcontextprotocol/server-filesystem \
  @modelcontextprotocol/server-github \
  @modelcontextprotocol/server-sqlite

EXPOSE 8090

CMD ["mcpd", "daemon", "--port", "8090", "--cors-origin", "*"]
```

```yaml
# docker-compose.desktop.yml
version: '3.8'

services:
  mcpd:
    build:
      context: .
      dockerfile: Dockerfile.desktop
    ports:
      - "8090:8090"
    volumes:
      - ${HOME}:/home/user:ro  # Read-only access to user files
      - mcpd-data:/data
    environment:
      - MCPD_DATA_DIR=/data
    restart: unless-stopped

volumes:
  mcpd-data:
```

## Security Considerations

### 1. CORS & Origin Validation
```go
// mcpd enhancement for secure CORS
func (s *Server) handleCORS(w http.ResponseWriter, r *http.Request) bool {
    origin := r.Header.Get("Origin")
    
    // Whitelist of allowed origins
    allowedOrigins := []string{
        "https://mcp-client.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
    }
    
    for _, allowed := range allowedOrigins {
        if origin == allowed {
            w.Header().Set("Access-Control-Allow-Origin", origin)
            w.Header().Set("Access-Control-Allow-Credentials", "true")
            return true
        }
    }
    
    return false
}
```

### 2. Local HTTPS with mkcert
```bash
# Generate local certificates
mkcert -install
mkcert localhost 127.0.0.1 ::1

# MCPD uses the certs
mcpd daemon \
  --cert /path/to/localhost.pem \
  --key /path/to/localhost-key.pem
```

### 3. Authentication Token
```typescript
// Frontend generates and stores a local token
const getOrCreateLocalToken = () => {
  let token = localStorage.getItem('mcpd-token');
  if (!token) {
    token = crypto.randomUUID();
    localStorage.setItem('mcpd-token', token);
  }
  return token;
};

// Include in all requests
fetch('https://localhost:8090/api/servers', {
  headers: {
    'Authorization': `Bearer ${getOrCreateLocalToken()}`
  }
});
```

## Web UI Modifications

### Auto-Discovery
```typescript
// frontend/src/hooks/useMCPDConnection.ts
import { useState, useEffect } from 'react';

const MCPD_URLS = [
  'https://localhost:8090',
  'http://localhost:8090',
  'http://127.0.0.1:8090',
];

export function useMCPDConnection() {
  const [mcpdUrl, setMcpdUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<'checking' | 'connected' | 'not-found'>('checking');
  
  useEffect(() => {
    checkMCPDAvailability();
  }, []);
  
  const checkMCPDAvailability = async () => {
    for (const url of MCPD_URLS) {
      try {
        const response = await fetch(`${url}/health`, {
          mode: 'cors',
          credentials: 'include',
        });
        
        if (response.ok) {
          setMcpdUrl(url);
          setStatus('connected');
          return;
        }
      } catch (error) {
        // Continue to next URL
      }
    }
    
    setStatus('not-found');
  };
  
  return { mcpdUrl, status, retry: checkMCPDAvailability };
}
```

### Connection Status UI
```tsx
// frontend/src/components/MCPDStatus.tsx
export function MCPDStatus() {
  const { mcpdUrl, status, retry } = useMCPDConnection();
  
  if (status === 'checking') {
    return (
      <div className="flex items-center gap-2 p-2 bg-yellow-50 rounded">
        <Loader2 className="w-4 h-4 animate-spin" />
        Connecting to local MCPD...
      </div>
    );
  }
  
  if (status === 'not-found') {
    return (
      <div className="p-4 bg-red-50 rounded">
        <h3 className="font-semibold text-red-800">MCPD Not Found</h3>
        <p className="text-sm text-red-600 mt-1">
          Please install and run MCPD locally to use MCP servers.
        </p>
        <div className="mt-3 space-y-2">
          <a 
            href="https://github.com/your-org/mcpd/releases"
            className="block px-3 py-2 bg-blue-500 text-white rounded text-center"
          >
            Download MCPD
          </a>
          <button 
            onClick={retry}
            className="w-full px-3 py-2 border border-gray-300 rounded"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }
  
  return (
    <div className="flex items-center gap-2 p-2 bg-green-50 rounded">
      <Check className="w-4 h-4 text-green-600" />
      <span className="text-sm text-green-800">
        Connected to MCPD at {mcpdUrl}
      </span>
    </div>
  );
}
```

## Advantages of This Approach

### ✅ Full MCP Capabilities
- Access to local file system
- Can run any NPM-based MCP server
- Full system integration (git, SSH, etc.)

### ✅ Simple Infrastructure
- No cloud compute costs
- No complex orchestration
- No multi-tenancy concerns

### ✅ Security
- User data stays local
- No cloud storage needed
- User controls their environment

### ✅ Developer Experience
- Works offline
- Fast local execution
- Easy debugging

## Challenges & Solutions

### Challenge 1: Browser Security (Mixed Content)
**Problem**: HTTPS site can't connect to HTTP localhost
**Solution**: Use local certificates with mkcert

### Challenge 2: Installation Friction
**Problem**: Users need to install MCPD
**Solution**: 
- Provide one-click installers
- Auto-download from web UI
- Bundle with Electron app

### Challenge 3: Cross-Platform Support
**Problem**: Different OS requirements
**Solution**: 
- Go binary for cross-platform
- Platform-specific installers
- Docker as fallback option

### Challenge 4: Firewall Issues
**Problem**: Corporate firewalls may block
**Solution**:
- Use standard ports (8080, 3000)
- Provide proxy configuration
- SSH tunnel option

## Distribution Strategy

### 1. Standalone Installers
```bash
# macOS
brew tap your-org/mcpd
brew install mcpd

# Windows (Chocolatey)
choco install mcpd

# Linux (Snap)
snap install mcpd
```

### 2. Electron Bundle
- Single app with UI + service
- Auto-updates via Electron
- System tray management

### 3. Progressive Deployment
1. **Phase 1**: Direct binary download
2. **Phase 2**: Package managers
3. **Phase 3**: Electron app
4. **Phase 4**: Native OS integration

## Implementation Checklist

- [ ] Modify MCPD to support CORS properly
- [ ] Add HTTPS support with self-signed certs
- [ ] Create Electron wrapper app
- [ ] Build installers for each platform
- [ ] Update web UI for local connection
- [ ] Add connection status indicators
- [ ] Create installation documentation
- [ ] Set up auto-update mechanism

## Comparison with Cloud Approach

| Aspect | Local MCPD | Cloud MCP |
|--------|------------|-----------|
| **Setup Complexity** | Medium (install required) | Low (just visit URL) |
| **Capabilities** | Full (all MCP servers) | Limited (remote only) |
| **Cost** | Free | $1-10/user/month |
| **Performance** | Fast (local) | Variable (network) |
| **Offline Support** | Yes | No |
| **Data Privacy** | Excellent (local) | Depends on provider |
| **Maintenance** | User updates | Automatic |

## Conclusion

The local MCPD service approach provides the **best of both worlds**:
- Cloud-hosted UI for easy access and updates
- Local service for full MCP capabilities
- No infrastructure costs
- Complete user control

This is ideal for developer tools and follows established patterns (Docker Desktop, GitHub Desktop, etc.).