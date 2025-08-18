# MCP Client Deployment Guide

## Current Status
Your deployment has been triggered to Railway. Here's what you need to do next:

## 1. Monitor Railway Deployment
Go to your Railway dashboard to check the build status:
- **Direct link to your project**: https://railway.com/project/066744cf-5fb4-46b4-a099-16be6c996a78
- Click on your backend service
- Check the "Deployments" tab for build logs
- Look for successful MCPD compilation and startup messages

## 2. Get Your Backend URL
Once the deployment completes:
- In the Railway service dashboard, find your public URL
- It will be something like: `mcp-backend-production.up.railway.app`
- Note this URL - you'll need it for the frontend configuration

## 3. Update Frontend Environment Variables
Once you have your Railway backend URL:

```bash
# Update the production environment file
echo "VITE_API_BASE_URL=https://YOUR-BACKEND-URL.railway.app" > frontend/.env.production
echo "VITE_WS_BASE_URL=wss://YOUR-BACKEND-URL.railway.app" >> frontend/.env.production
```

## 4. Redeploy Frontend to Vercel
After updating the environment variables:

```bash
cd frontend
vercel --prod
```

## 5. Configure Railway Environment Variables
In Railway dashboard, add these environment variables:
- `ALLOWED_ORIGINS`: Add your Vercel frontend URL (e.g., `https://your-app.vercel.app`)
- `ANTHROPIC_API_KEY`: Your Anthropic API key (if not already set)
- `OPENAI_API_KEY`: Your OpenAI API key (if using OpenAI models)

## 6. Test Your Deployment

### Check Backend Health:
```bash
curl https://YOUR-BACKEND-URL.railway.app/health
```

### Check MCPD Status:
```bash
curl https://YOUR-BACKEND-URL.railway.app/api/mcpd/status
```

### Test the Full System:
1. Open your Vercel frontend URL
2. Try sending a message
3. Check if MCP tools are available
4. Test adding an MCP server

## Troubleshooting

### If the Railway build fails:
- Check the build logs for Go compilation errors
- Ensure the mcpd directory is properly committed to git
- Verify the Dockerfile path is correct

### If MCPD doesn't start:
- Check Railway logs for supervisor errors
- Verify port 8090 is available internally
- Check MCPD logs in Railway dashboard

### If frontend can't connect to backend:
- Verify CORS settings include your Vercel URL
- Check that the backend URL in .env.production is correct
- Ensure WebSocket connections are allowed

## URLs and Links
- **Railway Dashboard**: https://railway.com/project/066744cf-5fb4-46b4-a099-16be6c996a78
- **Vercel Dashboard**: https://vercel.com/dashboard
- **Frontend URL**: (Will be shown after Vercel deployment)
- **Backend URL**: (Will be shown in Railway after deployment)

## Quick Commands Reference
```bash
# Check Railway deployment status
railway status

# View Railway logs (from Railway dashboard is easier)
railway logs

# Redeploy to Railway manually
./deploy-railway.sh

# Deploy frontend to Vercel
cd frontend && vercel --prod
```