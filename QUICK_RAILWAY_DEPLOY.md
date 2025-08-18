# Quick Railway Deployment Steps

## Option 1: Deploy WITHOUT MCPD (Easiest - Start Here)

1. **Rename config file**:
   ```bash
   mv railway-simple.json railway.json
   ```

2. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Add Railway deployment"
   git push origin main
   ```

3. **Deploy on Railway**:
   - Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repo
   - Railway will auto-deploy

4. **Set Environment Variables** in Railway dashboard:
   ```
   MCPD_ENABLED=false
   ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
   ```

5. **Test**: Visit `https://your-app.railway.app/health`

## Option 2: Deploy WITH MCPD (After Option 1 Works)

1. **Use full config**:
   ```bash
   mv railway.json railway-simple.json.backup
   cp railway.json.full railway.json  # Use the one with MCPD
   ```

2. **Update Railway environment**:
   ```
   MCPD_ENABLED=true
   CLOUD_MODE=true
   ```

3. **Redeploy**: Push any change to trigger rebuild

## What You Get

### Without MCPD:
- ✅ Chat interface works
- ✅ All LLM models work
- ❌ No MCP servers
- ❌ No tool calling

### With MCPD:
- ✅ Everything above PLUS
- ✅ Cloud MCP servers (memory, time)
- ✅ Tool calling support
- ✅ Remote MCP servers (Composio)

## Costs
- **Hobby plan**: $5/month (includes $5 usage)
- **Typical usage**: $10-20/month
- **Free tier**: Limited, may timeout

## Frontend (Separate)
Deploy frontend to Vercel:
1. Go to [vercel.com](https://vercel.com)
2. Import repo, set root to `/frontend`
3. Add env vars:
   ```
   VITE_API_BASE_URL=https://your-railway-app.railway.app
   VITE_WS_BASE_URL=wss://your-railway-app.railway.app
   ```

## Commands You'll Need

```bash
# Check if it's working
curl https://your-app.railway.app/health

# View logs
railway logs -f

# Redeploy
git push origin main
```

That's it! Start with Option 1 to get it running, then upgrade to Option 2 for full MCP support.