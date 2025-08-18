# Manual Railway Deployment Commands

## Step 1: Login to Railway
Open a new terminal and run:
```bash
railway login
```
This will open your browser. Complete the login.

## Step 2: Verify Login
```bash
railway whoami
```

## Step 3: Initialize Project
```bash
cd /Users/ameckes/Downloads/mcp-client-proto
railway init
```
Choose "Empty Project" when prompted.

## Step 4: Link to GitHub (Alternative)
Or link to existing GitHub repo:
```bash
railway link
```

## Step 5: Set Environment Variables
```bash
railway vars set PORT=8000
railway vars set MCPD_ENABLED=true
railway vars set CLOUD_MODE=true
railway vars set PYTHONUNBUFFERED=1
railway vars set ALLOWED_ORIGINS="https://*.vercel.app,http://localhost:3000,http://localhost:5173"
```

## Step 6: Deploy
```bash
railway up
```

## Step 7: Get URL
```bash
railway domain
```
Or open dashboard:
```bash
railway open
```

## Step 8: Check Logs
```bash
railway logs -f
```

## Files Being Used:
- `Dockerfile.railway-working` - Main Dockerfile
- `railway.toml` or `railway.json` - Config file
- `supervisord.conf` - Process manager

## Expected Output:
When successful, you'll see:
- "✓ MCPD is available at http://localhost:8090/api/v1"
- "✓ Installed memory MCP server"

## Test Your Deployment:
```bash
curl https://your-app.railway.app/health
```

Should return:
```json
{
  "status": "healthy",
  "mcpd_available": true,
  "mcpd_url": "http://localhost:8090/api/v1"
}
```