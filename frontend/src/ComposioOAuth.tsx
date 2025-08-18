import { useState, useEffect } from 'react'
import { Shield, ExternalLink, Check, Loader2 } from 'lucide-react'
import axios from 'axios'
import { API_BASE } from './config'

interface ComposioOAuthProps {
  onServerAdded: () => void
}

export default function ComposioOAuth({ onServerAdded }: ComposioOAuthProps) {
  const [isConnected, setIsConnected] = useState(false)
  const [entityId, setEntityId] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // Check if we're returning from OAuth callback
    const urlParams = new URLSearchParams(window.location.search)
    const authPath = window.location.pathname
    
    if (authPath === '/auth/success') {
      const entity = urlParams.get('entity_id')
      const tools = urlParams.get('tools')
      
      if (entity) {
        setEntityId(entity)
        setIsConnected(true)
        localStorage.setItem('composio_entity_id', entity)
        
        // Add the tools to our servers
        if (tools) {
          const toolList = tools.split(',')
          handleAddTools(entity, toolList)
        }
        
        // Clean up URL
        window.history.replaceState({}, '', '/')
      }
    } else if (authPath === '/auth/error') {
      const message = urlParams.get('message')
      console.error('Auth error:', message)
      window.history.replaceState({}, '', '/')
    }
    
    // Check if already connected
    const savedEntityId = localStorage.getItem('composio_entity_id')
    if (savedEntityId) {
      setEntityId(savedEntityId)
      setIsConnected(true)
    }
  }, [])

  const handleConnect = async () => {
    setLoading(true)
    
    try {
      // Get OAuth URL from backend
      const response = await axios.get(`${API_BASE}/auth/composio/login`)
      const { auth_url } = response.data
      
      // Redirect to Composio OAuth
      window.location.href = auth_url
    } catch (error) {
      console.error('Failed to initiate OAuth:', error)
      setLoading(false)
    }
  }

  const handleAddTools = async (entity: string, tools: string[]) => {
    try {
      await axios.post(`${API_BASE}/auth/composio/add-tools`, {
        entity_id: entity,
        tools: tools
      })
      onServerAdded()
    } catch (error) {
      console.error('Failed to add tools:', error)
    }
  }

  const handleDisconnect = () => {
    localStorage.removeItem('composio_entity_id')
    setIsConnected(false)
    setEntityId('')
  }

  if (isConnected) {
    return (
      <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Check className="w-4 h-4 text-green-600" />
            <span className="text-sm font-medium text-green-800">
              Connected to Composio
            </span>
            <span className="text-xs text-green-600">
              ({entityId})
            </span>
          </div>
          <button
            onClick={handleDisconnect}
            className="text-xs text-red-600 hover:underline"
          >
            Disconnect
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mb-6">
      <button
        onClick={handleConnect}
        disabled={loading}
        className="w-full p-4 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg hover:from-blue-600 hover:to-purple-700 transition-all shadow-lg hover:shadow-xl disabled:opacity-50"
      >
        <div className="flex items-center justify-center gap-3">
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="font-medium">Connecting...</span>
            </>
          ) : (
            <>
              <Shield className="w-5 h-5" />
              <span className="font-medium">Connect with Composio</span>
              <ExternalLink className="w-4 h-4" />
            </>
          )}
        </div>
        <p className="text-sm opacity-90 mt-2">
          Sign in to enable GitHub, Slack, Notion & 25+ tool integrations
        </p>
      </button>
      
      <p className="text-xs text-gray-500 text-center mt-3">
        Secure OAuth authentication • No API keys required
      </p>
    </div>
  )
}