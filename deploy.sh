#!/bin/bash
set -e

echo "🚀 Railway Deployment Script for MCP Client with MCPD"
echo "=================================================="

# Step 1: Check Railway CLI
echo "1️⃣ Checking Railway CLI..."
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Installing..."
    brew install railway || npm install -g @railway/cli
else
    echo "✅ Railway CLI found: $(railway --version)"
fi

# Step 2: Login to Railway
echo ""
echo "2️⃣ Checking Railway login..."
if ! railway whoami &> /dev/null; then
    echo "📝 Please login to Railway:"
    echo "   Run: railway login"
    echo "   Then run this script again."
    exit 1
else
    echo "✅ Logged in as: $(railway whoami)"
fi

# Step 3: Initialize or link project
echo ""
echo "3️⃣ Initializing Railway project..."
if [ ! -f ".railway/config.json" ]; then
    echo "Creating new Railway project..."
    railway init
else
    echo "✅ Railway project already configured"
fi

# Step 4: Set environment variables
echo ""
echo "4️⃣ Setting environment variables..."
railway vars set PORT=8000
railway vars set MCPD_ENABLED=true
railway vars set CLOUD_MODE=true
railway vars set PYTHONUNBUFFERED=1
railway vars set ALLOWED_ORIGINS="https://*.vercel.app,http://localhost:3000,http://localhost:5173,http://localhost:5174"
echo "✅ Environment variables set"

# Step 5: Deploy
echo ""
echo "5️⃣ Deploying to Railway..."
echo "Using Dockerfile.railway-working for deployment"

# Make sure we're using the right Dockerfile
if [ -f "railway.toml" ]; then
    echo "✅ Using railway.toml configuration"
elif [ -f "railway.json" ]; then
    echo "✅ Using railway.json configuration"
else
    echo "⚠️  No Railway config found, creating railway.json..."
    cat > railway.json << 'EOF'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile.railway-working"
  },
  "deploy": {
    "numReplicas": 1,
    "healthcheckPath": "/health",
    "healthcheckTimeout": 60,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
EOF
fi

# Deploy
railway up

echo ""
echo "6️⃣ Getting deployment URL..."
sleep 5
DEPLOY_URL=$(railway domain 2>/dev/null || echo "Check Railway dashboard for URL")

echo ""
echo "✅ Deployment complete!"
echo "=================================================="
echo "🔗 Your app URL: $DEPLOY_URL"
echo ""
echo "📝 Next steps:"
echo "1. Check health: curl https://your-app.railway.app/health"
echo "2. View logs: railway logs -f"
echo "3. Open dashboard: railway open"
echo ""
echo "🎉 Your MCP Client with MCPD is now live!"