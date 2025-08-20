import { useState, useEffect, useRef } from 'react'
import { Shield, Plus, Check, AlertCircle, ExternalLink, Loader2, X } from 'lucide-react'
import axios from 'axios'
import { API_BASE } from './config'

interface ComposioOAuthFlowProps {
  onServerAdded: () => void
}

const AVAILABLE_APPS = [
  { id: 'gmail', name: 'Gmail', icon: '📧', description: 'Read, send, and manage emails' },
  { id: 'github', name: 'GitHub', icon: '🐙', description: 'Create issues, manage repos' },
  { id: 'slack', name: 'Slack', icon: '💬', description: 'Send messages, search chats' },
  { id: 'notion', name: 'Notion', icon: '📝', description: 'Create pages, update databases' },
]

export default function ComposioOAuthFlow({ onServerAdded }: ComposioOAuthFlowProps) {
  const [userId, setUserId] = useState('')
  const [connecting, setConnecting] = useState<string | null>(null)
  const [connectedApps, setConnectedApps] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [checkingConnections, setCheckingConnections] = useState(false)
  const onServerAddedRef = useRef(onServerAdded)
  
  // Update ref when prop changes
  useEffect(() => {
    onServerAddedRef.current = onServerAdded
  }, [onServerAdded])

  useEffect(() => {
    // Generate or retrieve user ID
    let storedUserId = localStorage.getItem('composio_user_id')
    if (!storedUserId) {
      storedUserId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      localStorage.setItem('composio_user_id', storedUserId)
    }
    setUserId(storedUserId)
    checkUserConnections(storedUserId)

    // Check if we're returning from OAuth callback
    const urlParams = new URLSearchParams(window.location.search)
    if (urlParams.get('composio_connected')) {
      const app = urlParams.get('app')
      if (app) {
        handlePostConnection(app)
      }
      // Clean up URL
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  const checkUserConnections = async (uid: string) => {
    setCheckingConnections(true)
    try {
      const response = await axios.get(`${API_BASE}/composio/connections/${uid}`)
      if (response.data.connections && response.data.connections.length > 0) {
        const connected = new Set(response.data.connections.map((c: any) => c.app.toLowerCase()))
        setConnectedApps(connected)
        
        // Ensure MCP servers are registered for all connected apps
        let serversAdded = false
        for (const connection of response.data.connections) {
          const appName = connection.app.toLowerCase()
          try {
            const serverResponse = await axios.post(`${API_BASE}/composio/add-mcp-server`, {
              user_id: uid,
              app_name: appName
            })
            if (serverResponse.data.added) {
              console.log(`Ensured MCP server for ${appName}`)
              serversAdded = true
            }
          } catch (err) {
            console.error(`Failed to ensure MCP server for ${appName}:`, err)
          }
        }
        
        // Refresh servers list if we added any
        if (serversAdded) {
          setTimeout(() => {
            onServerAddedRef.current()
          }, 500)
        }
      }
    } catch (error) {
      console.log('No existing connections or Composio not configured')
    } finally {
      setCheckingConnections(false)
    }
  }

  const handleConnectApp = async (appId: string) => {
    setConnecting(appId)
    setError(null)

    try {
      // Initiate OAuth connection through our backend
      const response = await axios.post(`${API_BASE}/composio/connect`, {
        user_id: userId,
        app_name: appId,
        callback_url: `${window.location.origin}?composio_connected=true&app=${appId}`
      })

      if (response.data.mode === 'oauth' && response.data.redirect_url) {
        // Save state before redirecting
        sessionStorage.setItem('composio_connecting_app', appId)
        // Redirect to Composio OAuth
        window.location.href = response.data.redirect_url
      } else if (response.data.mode === 'direct') {
        // Fallback to direct MCP URL mode
        await handleDirectMode(appId, response.data.mcp_url)
      }
    } catch (err: any) {
      setError(`Failed to connect ${appId}. ${err.response?.data?.error || 'Please try again.'}`)
      setConnecting(null)
    }
  }

  const handleDirectMode = async (appId: string, mcpUrl: string) => {
    try {
      // Add as MCP server
      await axios.post(`${API_BASE}/composio/add-mcp-server`, {
        user_id: userId,
        app_name: appId
      })

      // Also add to remote servers
      await axios.post(`${API_BASE}/add-remote-server`, {
        input: mcpUrl
      })

      setConnectedApps(prev => new Set([...prev, appId]))
      onServerAddedRef.current()
      setConnecting(null)
    } catch (err) {
      throw err
    }
  }

  const handlePostConnection = async (appId: string) => {
    try {
      // Add the connected app as an MCP server
      const response = await axios.post(`${API_BASE}/composio/add-mcp-server`, {
        user_id: userId,
        app_name: appId
      })

      if (response.data.added) {
        setConnectedApps(prev => new Set([...prev, appId]))
        
        // Wait a moment for server to be fully registered, then refresh
        setTimeout(() => {
          onServerAddedRef.current()
        }, 500)
        
        // Show success message
        setError(null)
      } else {
        throw new Error('Failed to add MCP server')
      }
    } catch (err) {
      setError(`Connected to ${appId} but failed to add as MCP server`)
    }
  }

  const handleDisconnectApp = async (appId: string) => {
    // For now, just remove from local state
    // In production, would also disconnect from Composio
    setConnectedApps(prev => {
      const newSet = new Set(prev)
      newSet.delete(appId)
      return newSet
    })
  }

  return (
    <div className="mb-6 space-y-3">
      <div className="p-4 bg-white rounded-lg border border-gray-200">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="w-5 h-5 text-blue-600" />
          <h3 className="font-medium text-gray-900">Connect Your Tools</h3>
          {checkingConnections && (
            <Loader2 className="w-4 h-4 animate-spin text-gray-500 ml-auto" />
          )}
        </div>

        <p className="text-sm text-gray-600 mb-4">
          Connect your accounts securely through Composio. Click any tool below to authenticate.
        </p>

        <div className="grid grid-cols-2 gap-3">
          {AVAILABLE_APPS.map((app) => {
            const isConnected = connectedApps.has(app.id)
            const isConnecting = connecting === app.id

            return (
              <div
                key={app.id}
                className={`relative p-3 rounded-lg border transition-all ${
                  isConnected
                    ? 'bg-green-50 border-green-300'
                    : isConnecting
                    ? 'bg-blue-50 border-blue-300'
                    : 'bg-white border-gray-200 hover:border-blue-400 hover:bg-blue-50'
                }`}
              >
                <button
                  onClick={() => !isConnected && !isConnecting && handleConnectApp(app.id)}
                  disabled={isConnected || isConnecting}
                  className="w-full text-left"
                >
                  <div className="flex items-start gap-2">
                    <span className="text-2xl">{app.icon}</span>
                    <div className="flex-1">
                      <div className="font-medium text-sm">{app.name}</div>
                      <div className="text-xs text-gray-500">{app.description}</div>
                    </div>
                    {isConnecting ? (
                      <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                    ) : isConnected ? (
                      <Check className="w-4 h-4 text-green-600" />
                    ) : (
                      <Plus className="w-4 h-4 text-gray-400" />
                    )}
                  </div>
                </button>
                
                {isConnected && (
                  <button
                    onClick={() => handleDisconnectApp(app.id)}
                    className="absolute top-1 right-1 p-1 text-gray-400 hover:text-red-600 opacity-0 hover:opacity-100 transition-opacity"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            )
          })}
        </div>

        {connectedApps.size > 0 && (
          <div className="mt-4 p-2 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-green-700">
              <Check className="w-4 h-4" />
              ✨ {connectedApps.size} tool{connectedApps.size !== 1 ? 's' : ''} ready for AI assistant
            </div>
          </div>
        )}

        {error && (
          <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      <div className="text-center">
        <p className="text-xs text-gray-500">
          Powered by{' '}
          <a
            href="https://composio.dev"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline inline-flex items-center gap-1"
          >
            Composio
            <ExternalLink className="w-3 h-3" />
          </a>
          {' '}• Secure OAuth authentication
        </p>
      </div>
    </div>
  )
}