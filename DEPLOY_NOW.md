# Deploy to Railway with MCPD - Quick Guide

## What You're Getting
- ✅ Full MCPD support in the cloud
- ✅ MCP servers (memory, time, etc.)
- ✅ Tool calling with Claude
- ✅ WebSocket support
- ✅ Auto-scaling and monitoring

## Step 1: Prepare Your Code

```bash
# Commit all changes
git add .
git commit -m "Add Railway deployment with MCPD support"
git push origin main
```

## Step 2: Deploy to Railway

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your `mcp-client-proto` repository
5. Railway will detect the configuration automatically

## Step 3: Set Environment Variables

In Railway dashboard, add these variables:

```env
PORT=8000
MCPD_ENABLED=true
CLOUD_MODE=true
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173
```

Optional API keys (users can provide via UI):
```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Step 4: Monitor Deployment

Watch the build logs. You should see:
- "Building MCPD from source..."
- "✓ MCPD is available at http://localhost:8090/api/v1"
- "✓ Installed memory MCP server"

## Step 5: Test Your Deployment

```bash
# Check health
curl https://your-app.railway.app/health

# Expected response:
{
  "status": "healthy",
  "mcpd_available": true,
  "mcpd_url": "http://localhost:8090/api/v1"
}
```

## Step 6: Deploy Frontend (Optional)

If you want to deploy the frontend to Vercel:

1. Go to [vercel.com](https://vercel.com)
2. Import your repository
3. Set root directory to `/frontend`
4. Add environment variables:
   ```
   VITE_API_BASE_URL=https://your-app.railway.app
   VITE_WS_BASE_URL=wss://your-app.railway.app
   ```

## Files Being Used

- **`Dockerfile.railway-working`** - Builds MCPD from source
- **`railway.toml`** or **`railway.json`** - Railway configuration
- **`supervisord.conf`** - Manages both backend and MCPD processes

## Troubleshooting

### If MCPD doesn't start:
1. Check logs: `railway logs`
2. Look for: "MCPD is available" message
3. Verify go.mod has `go 1.21` (not 1.24.4)

### If build fails:
- Railway uses `railway.toml` or `railway.json`
- Make sure it points to `Dockerfile.railway-working`

### WebSocket issues:
- Railway supports WebSockets by default
- Ensure frontend uses `wss://` not `ws://`

## Cost
- **Hobby plan**: $5/month base
- **Typical usage**: $10-20/month total
- **Free trial**: $5 credit available

## Success Indicators
✅ `/health` shows `mcpd_available: true`
✅ WebSocket connects successfully
✅ Can use MCP tools in chat
✅ No errors in Railway logs

## Quick Commands

```bash
# View logs
railway logs -f

# Redeploy
git push origin main

# Connect to service
railway run bash
```

That's it! Your app will be live with full MCPD support in about 5 minutes.