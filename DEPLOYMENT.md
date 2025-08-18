# Deployment Guide

This guide explains how to deploy the MCP Client to production using Vercel (frontend) and Railway (backend).

## Prerequisites

- GitHub account with the repository
- [Vercel account](https://vercel.com)
- [Railway account](https://railway.app)
- API keys for the LLM providers you want to use

## Backend Deployment (Railway)

### 1. Deploy to Railway

1. Go to [Railway](https://railway.app) and sign in
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `mcp-client-proto` repository
4. Railway will auto-detect the backend folder
5. Set the root directory to `/backend`

### 2. Configure Environment Variables

In Railway dashboard, add these environment variables:

```env
# Required
PORT=8000
ALLOWED_ORIGINS=https://your-frontend.vercel.app

# Optional - for MCPD support (not recommended for production)
MCPD_ENABLED=false

# Optional - for persistent storage
USE_PERSISTENT_STORAGE=false
# REDIS_URL=your-redis-url (if using Redis)

# Optional - default API keys (users should provide their own)
# ANTHROPIC_API_KEY=your-key
# OPENAI_API_KEY=your-key
```

### 3. Deploy

Railway will automatically deploy your backend. Note the URL (e.g., `https://mcp-client-backend.railway.app`)

## Frontend Deployment (Vercel)

### 1. Deploy to Vercel

1. Go to [Vercel](https://vercel.com) and sign in
2. Click "New Project" → Import your Git repository
3. Select your `mcp-client-proto` repository
4. Set the root directory to `/frontend`
5. Framework preset: Vite

### 2. Configure Environment Variables

In Vercel dashboard, add these environment variables:

```env
VITE_API_BASE_URL=https://your-backend.railway.app
VITE_WS_BASE_URL=wss://your-backend.railway.app
VITE_ENABLE_LOCAL_MCPD=false
```

### 3. Deploy

Click "Deploy" and Vercel will build and deploy your frontend.

## Post-Deployment Setup

### 1. Update CORS Origins

Go back to Railway and update the `ALLOWED_ORIGINS` environment variable to include your Vercel frontend URL:

```
ALLOWED_ORIGINS=https://your-app.vercel.app
```

### 2. Test the Connection

1. Visit your Vercel frontend URL
2. Open the API Keys modal and enter your LLM provider API keys
3. Try sending a message to verify the WebSocket connection works

## Important Considerations for Production

### Security

1. **API Keys**: Users should provide their own API keys. Never store API keys in the frontend code.
2. **CORS**: Properly configure CORS to only allow your frontend domain
3. **Rate Limiting**: Consider implementing rate limiting on the backend
4. **Authentication**: For a production app, implement proper user authentication

### Limitations

1. **Local MCPD**: The local MCPD daemon won't work in production. Only remote MCP servers (like Composio) will work.
2. **File System Access**: Local file system MCP servers won't work in production
3. **WebSocket Scaling**: For high traffic, consider using a WebSocket service like Pusher or Ably

### Remote MCP Servers

In production, users can still use remote MCP servers like:
- Composio (https://composio.dev)
- Custom HTTP/HTTPS MCP endpoints
- Any MCP server exposed via HTTP

### Persistent Storage

For production, consider using:
- **Redis**: For storing remote server configurations
- **PostgreSQL**: For user settings and conversation history
- **S3/CloudStorage**: For file uploads

## Monitoring

### Railway
- Use Railway's built-in metrics
- Set up alerts for high memory/CPU usage
- Monitor WebSocket connections

### Vercel
- Use Vercel Analytics
- Monitor Core Web Vitals
- Set up error tracking (e.g., Sentry)

## Updating

### Backend (Railway)
- Push changes to your GitHub repository
- Railway will auto-deploy

### Frontend (Vercel)
- Push changes to your GitHub repository
- Vercel will auto-deploy

## Troubleshooting

### WebSocket Connection Issues
- Ensure `ALLOWED_ORIGINS` includes your frontend URL
- Check that `wss://` protocol is used in production
- Verify Railway supports WebSocket connections (it does)

### CORS Errors
- Double-check `ALLOWED_ORIGINS` in Railway
- Ensure the frontend is using the correct backend URL

### API Key Issues
- Verify API keys are correctly set in the frontend
- Check browser console for errors
- Ensure the backend is properly receiving the keys

## Cost Considerations

### Vercel (Frontend)
- **Free tier**: Perfect for personal projects
- Includes 100GB bandwidth/month
- Unlimited deployments

### Railway (Backend)
- **Free tier**: $5 credit/month
- **Hobby tier**: $5/month (should be sufficient)
- Pay for what you use (CPU, Memory, Network)

### Estimated Monthly Cost
- **Low traffic** (personal use): ~$5-10/month
- **Medium traffic** (small team): ~$20-50/month
- **High traffic** (public app): Consider enterprise solutions

## Alternative Deployment Options

### Backend Alternatives
- **Render**: Similar to Railway, good free tier
- **Fly.io**: Great for WebSocket apps
- **Google Cloud Run**: Serverless, scales to zero
- **AWS App Runner**: Managed container service

### Frontend Alternatives
- **Netlify**: Similar to Vercel
- **Cloudflare Pages**: Fast, global CDN
- **GitHub Pages**: Free, but static only
- **AWS Amplify**: Full-stack platform