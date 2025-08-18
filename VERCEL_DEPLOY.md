# Deploy Frontend to Vercel

## Prerequisites
- Railway backend deployed and running
- Railway backend URL (e.g., `https://mcp-client-mcpd.railway.app`)

## Step 1: Push to GitHub
```bash
git add .
git commit -m "Add Vercel deployment configuration"
git push origin main
```

## Step 2: Deploy to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Click **"Add New Project"**
3. Import your GitHub repository
4. Configure:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

## Step 3: Set Environment Variables

In Vercel, add these environment variables:

```env
VITE_API_BASE_URL=https://your-backend.railway.app
VITE_WS_BASE_URL=wss://your-backend.railway.app
```

Replace `your-backend` with your actual Railway URL!

## Step 4: Deploy

Click **"Deploy"** and wait for the build to complete.

## Step 5: Update Railway CORS

Go back to Railway and update the `ALLOWED_ORIGINS` environment variable:

```bash
railway variables --set "ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173"
```

Or in Railway dashboard:
```
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173
```

## Testing

1. Visit your Vercel URL
2. Open browser console
3. Check that WebSocket connects to Railway backend
4. Try sending a message

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│   Vercel            │  HTTPS  │   Railway            │
│   Frontend          │────────▶│   Backend + MCPD     │
│   (React)           │   WSS   │   (FastAPI + Go)     │
└─────────────────────┘         └──────────────────────┘
```

## Troubleshooting

### CORS Errors
- Make sure `ALLOWED_ORIGINS` in Railway includes your Vercel URL
- Check that you're using `https://` not `http://`

### WebSocket Connection Failed
- Ensure you're using `wss://` not `ws://` for production
- Check Railway backend is running: `https://your-backend.railway.app/health`

### API Keys
Users will provide their own API keys through the UI - no need to set them in Vercel.