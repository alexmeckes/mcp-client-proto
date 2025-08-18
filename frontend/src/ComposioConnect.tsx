import { useState, useEffect } from 'react'
import { Shield, Check, AlertCircle, Loader2, Plus, Trash2, ExternalLink } from 'lucide-react'
import axios from 'axios'
import { API_BASE } from './config'

interface ComposioTool {
  name: string
  app: string
  description: string
  enabled: boolean
  url?: string
}

interface ComposioConnectProps {
  onServerAdded: () => void
}

export default function ComposioConnect({ onServerAdded }: ComposioConnectProps) {
  const [isConnected, setIsConnected] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [entityId, setEntityId] = useState('')
  const [availableTools, setAvailableTools] = useState<ComposioTool[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showConnect, setShowConnect] = useState(false)
  const [addingTool, setAddingTool] = useState<string | null>(null)

  // Check if already connected on mount
  useEffect(() => {
    const savedApiKey = localStorage.getItem('composio_api_key')
    const savedEntityId = localStorage.getItem('composio_entity_id')
    if (savedApiKey && savedEntityId) {
      setApiKey(savedApiKey)
      setEntityId(savedEntityId)
      setIsConnected(true)
      fetchAvailableTools(savedApiKey, savedEntityId)
    }
  }, [])

  const fetchAvailableTools = async (key: string, entity: string) => {
    try {
      // For now, we'll use predefined popular tools
      // In a real implementation, this would fetch from Composio API
      const tools: ComposioTool[] = [
        { name: 'GitHub', app: 'github', description: 'Repository management, issues, PRs', enabled: false },
        { name: 'Slack', app: 'slack', description: 'Send messages, manage channels', enabled: false },
        { name: 'Gmail', app: 'gmail', description: 'Send emails, manage inbox', enabled: false },
        { name: 'Google Calendar', app: 'googlecalendar', description: 'Create events, manage calendars', enabled: false },
        { name: 'Notion', app: 'notion', description: 'Create pages, manage databases', enabled: false },
        { name: 'Linear', app: 'linear', description: 'Issue tracking and project management', enabled: false },
        { name: 'Discord', app: 'discord', description: 'Send messages, manage servers', enabled: false },
        { name: 'Jira', app: 'jira', description: 'Issue tracking and agile management', enabled: false },
      ]
      
      // Check which tools are already added
      const response = await axios.get(`${API_BASE}/remote-servers`)
      const addedServers = response.data.servers || []
      
      tools.forEach(tool => {
        const url = `https://mcp.composio.dev/${tool.app}/mcp?customerId=${entity}`
        tool.url = url
        tool.enabled = addedServers.some((s: any) => s.url === url)
      })
      
      setAvailableTools(tools)
    } catch (err) {
      console.error('Failed to fetch tools:', err)
    }
  }

  const handleConnect = async () => {
    if (!apiKey.trim() || !entityId.trim()) {
      setError('Please enter both API Key and Entity ID')
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Save credentials locally
      localStorage.setItem('composio_api_key', apiKey.trim())
      localStorage.setItem('composio_entity_id', entityId.trim())
      
      setIsConnected(true)
      await fetchAvailableTools(apiKey.trim(), entityId.trim())
      setShowConnect(false)
    } catch (err: any) {
      setError('Failed to connect to Composio')
    } finally {
      setLoading(false)
    }
  }

  const handleDisconnect = () => {
    localStorage.removeItem('composio_api_key')
    localStorage.removeItem('composio_entity_id')
    setIsConnected(false)
    setApiKey('')
    setEntityId('')
    setAvailableTools([])
  }

  const handleToggleTool = async (tool: ComposioTool) => {
    if (!tool.url) return
    
    setAddingTool(tool.app)
    
    try {
      if (tool.enabled) {
        // Remove the server
        const response = await axios.get(`${API_BASE}/remote-servers`)
        const servers = response.data.servers || []
        const server = servers.find((s: any) => s.url === tool.url)
        
        if (server) {
          await axios.delete(`${API_BASE}/remote-servers/${server.id}`)
        }
      } else {
        // Add the server
        await axios.post(`${API_BASE}/add-remote-server`, {
          input: tool.url
        })
      }
      
      // Refresh the tools list
      await fetchAvailableTools(apiKey, entityId)
      onServerAdded()
    } catch (err: any) {
      setError(`Failed to ${tool.enabled ? 'remove' : 'add'} ${tool.name}`)
    } finally {
      setAddingTool(null)
    }
  }

  if (!isConnected) {
    return (
      <div className="mb-6">
        <button
          onClick={() => setShowConnect(true)}
          className="w-full p-4 border-2 border-dashed border-blue-300 rounded-lg hover:border-blue-400 hover:bg-blue-50 transition-all group"
        >
          <div className="flex items-center justify-center gap-3">
            <Shield className="w-5 h-5 text-blue-600" />
            <span className="font-medium text-blue-600">Connect with Composio</span>
          </div>
          <p className="text-sm text-gray-600 mt-2">
            Connect your Composio account to enable 25+ integrations
          </p>
        </button>

        {showConnect && (
          <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center" onClick={() => setShowConnect(false)}>
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
              <div className="flex items-center gap-3 mb-4">
                <Shield className="w-6 h-6 text-blue-600" />
                <h3 className="text-lg font-semibold">Connect Composio Account</h3>
              </div>

              <p className="text-sm text-gray-600 mb-4">
                Enter your Composio credentials to enable tool integrations. You can find these in your Composio dashboard.
              </p>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    API Key
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Your Composio API Key"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Entity ID / Customer ID
                  </label>
                  <input
                    type="text"
                    value={entityId}
                    onChange={(e) => setEntityId(e.target.value)}
                    placeholder="default or your-entity-id"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div className="text-xs text-gray-500">
                  Don't have an account? 
                  <a 
                    href="https://app.composio.dev" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="ml-1 text-blue-600 hover:underline inline-flex items-center gap-1"
                  >
                    Sign up at Composio
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>

              {error && (
                <div className="mt-4 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="flex gap-2 mt-6">
                <button
                  onClick={handleConnect}
                  disabled={loading || !apiKey.trim() || !entityId.trim()}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      Connect
                    </>
                  )}
                </button>
                <button
                  onClick={() => {
                    setShowConnect(false)
                    setError(null)
                  }}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <Shield className="w-4 h-4 text-green-600" />
          <span className="text-green-600">Composio Connected</span>
        </h3>
        <button
          onClick={handleDisconnect}
          className="text-xs text-red-600 hover:underline"
        >
          Disconnect
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {availableTools.map((tool) => (
          <div
            key={tool.app}
            className={`p-3 border rounded-lg transition-all ${
              tool.enabled 
                ? 'border-green-400 bg-green-50' 
                : 'border-gray-200 hover:border-blue-400 hover:bg-blue-50'
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-sm">{tool.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">{tool.description}</div>
              </div>
              <button
                onClick={() => handleToggleTool(tool)}
                disabled={addingTool === tool.app}
                className={`p-2 rounded-lg transition-all ${
                  tool.enabled
                    ? 'text-red-600 hover:bg-red-100'
                    : 'text-blue-600 hover:bg-blue-100'
                } disabled:opacity-50`}
              >
                {addingTool === tool.app ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : tool.enabled ? (
                  <Trash2 className="w-4 h-4" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>

      {availableTools.filter(t => t.enabled).length > 0 && (
        <div className="mt-3 text-xs text-green-600">
          ✓ {availableTools.filter(t => t.enabled).length} tool{availableTools.filter(t => t.enabled).length !== 1 ? 's' : ''} enabled
        </div>
      )}
    </div>
  )
}