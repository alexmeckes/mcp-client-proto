# Railway Deployment Guide for MCP Client with Cloud MCPD

This guide will help you deploy the MCP Client to Railway with embedded MCPD support.

## Prerequisites

1. [Railway account](https://railway.app)
2. [Railway CLI](https://docs.railway.app/develop/cli) (optional but recommended)
3. GitHub repository with your code

## Step 1: Prepare Your Repository

Make sure your repository structure looks like this:
```
mcp-client-proto/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   └── config.py
│   ├── requirements.txt
│   ├── Dockerfile.railway
│   └── supervisord.conf
├── mcpd/
│   ├── cmd/
│   ├── go.mod
│   └── go.sum
├── frontend/
│   └── (your frontend files)
└── railway.json
```

## Step 2: Deploy to Railway

### Option A: Deploy via GitHub (Recommended)

1. Push your code to GitHub:
```bash
git add .
git commit -m "Add Railway deployment configuration"
git push origin main
```

2. Go to [Railway Dashboard](https://railway.app/dashboard)

3. Click "New Project" → "Deploy from GitHub repo"

4. Select your repository

5. Railway will auto-detect the configuration and start building

### Option B: Deploy via CLI

1. Install Railway CLI:
```bash
brew install railway
# or
npm install -g @railway/cli
```

2. Login to Railway:
```bash
railway login
```

3. Initialize project:
```bash
railway init
```

4. Deploy:
```bash
railway up
```

## Step 3: Configure Environment Variables

In the Railway dashboard, go to your service settings and add these environment variables:

```env
# Required
PORT=8000
MCPD_ENABLED=true
CLOUD_MODE=true
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173

# Optional - API Keys (users can provide via UI)
ANTHROPIC_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here

# MCPD Configuration
MCPD_BASE_URL=http://localhost:8090/api/v1
MCPD_HEALTH_CHECK_URL=http://localhost:8090/health
```

## Step 4: Monitor Deployment

1. Watch the build logs in Railway dashboard
2. Once deployed, Railway will provide a URL like: `https://your-app.railway.app`
3. Check the health endpoint: `https://your-app.railway.app/health`

Expected response:
```json
{
  "status": "healthy",
  "mcpd_available": true,
  "mcpd_url": "http://localhost:8090/api/v1"
}
```

## Step 5: Deploy Frontend (Vercel)

1. Go to [Vercel](https://vercel.com)
2. Import your repository
3. Set root directory to `/frontend`
4. Add environment variables:
```env
VITE_API_BASE_URL=https://your-app.railway.app
VITE_WS_BASE_URL=wss://your-app.railway.app
```
5. Deploy

## Step 6: Update CORS

Go back to Railway and update the `ALLOWED_ORIGINS` environment variable to include your Vercel URL:
```
ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

## Troubleshooting

### Build Fails

If the build fails with "mcpd directory not found":
1. Ensure the mcpd directory is in your repository
2. Check that `railway.json` has `"buildContext": "."`

### MCPD Not Starting

Check the logs for MCPD startup:
```bash
railway logs
```

Look for:
- "✓ MCPD is available at http://localhost:8090/api/v1"
- "✓ Installed memory MCP server"

### WebSocket Connection Issues

1. Ensure your frontend is using `wss://` (not `ws://`) for production
2. Check that CORS origins are correctly configured
3. Verify Railway supports WebSocket (it does by default)

### Memory/CPU Issues

Railway's free tier includes:
- 512 MB RAM
- 0.5 vCPU

If you need more resources:
1. Go to service settings
2. Adjust resource limits
3. Consider upgrading to a paid plan

## Monitoring

### View Logs
```bash
railway logs -f
```

### Check Metrics
In Railway dashboard:
- CPU usage
- Memory usage
- Network traffic
- Response times

## Updating Your Deployment

### Via GitHub
```bash
git add .
git commit -m "Update feature"
git push origin main
```
Railway will automatically redeploy.

### Via CLI
```bash
railway up
```

## Cost Estimates

- **Hobby Plan**: $5/month (includes $5 of usage)
- **Typical usage**: ~$10-20/month for this application
- **Scale to zero**: Not available (app runs 24/7)

## Alternative: Deploy Without MCPD

If you want to deploy without MCPD initially:

1. Use `Dockerfile.simple` instead:
```json
// railway.json
{
  "build": {
    "dockerfilePath": "backend/Dockerfile.simple"
  }
}
```

2. Set environment variable:
```env
MCPD_ENABLED=false
```

This will deploy just the backend without MCP server capabilities.

## Next Steps

1. **Add custom domain**: In Railway settings → Domains
2. **Set up monitoring**: Consider adding Sentry or LogDNA
3. **Add Redis**: For persistent storage of server configurations
4. **Scale horizontally**: Add more replicas if needed

## Support

- [Railway Documentation](https://docs.railway.app)
- [Railway Discord](https://discord.gg/railway)
- [GitHub Issues](https://github.com/your-username/mcp-client-proto/issues)