#!/bin/bash
set -e

echo "🚀 Deploying to Railway with MCPD support"
echo "========================================="

# Option 1: Try with first service
echo "Attempting deployment..."
railway up --service 1 --detach 2>/dev/null || {
    echo "Failed with service 1, trying service 2..."
    railway up --service 2 --detach 2>/dev/null || {
        echo "❌ Could not auto-deploy. Please run manually:"
        echo ""
        echo "1. Run: railway up"
        echo "2. Select the backend service when prompted"
        echo "3. Wait for deployment to complete"
        echo ""
        echo "Or in Railway dashboard:"
        echo "1. Go to: https://railway.com/project/066744cf-5fb4-46b4-a099-16be6c996a78"
        echo "2. Click on your service"
        echo "3. Go to Settings → Triggers"
        echo "4. Click 'Deploy' or enable 'Auto Deploy'"
    }
}

echo ""
echo "Check deployment status:"
echo "railway logs --tail 20"