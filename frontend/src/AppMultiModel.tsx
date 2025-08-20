import { useState, useEffect, useRef } from 'react'
import { Send, Server, Wrench, Bot, User, Loader2, AlertCircle, Settings, Save, Plus, X, Copy, Check, Trash2, Search, Keyboard, ChevronDown, ChevronUp, RefreshCw, Key, Brain, Package, Globe, HardDrive, Lock, Unlock, ExternalLink } from 'lucide-react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
// import ServerMarketplace from './ServerMarketplace' // MCPD removed
import ComposioOAuthFlow from './ComposioOAuthFlow'
import QuickAddServer from './QuickAddServer'

import { API_BASE, WS_BASE } from './config'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  toolCalls?: ToolCall[]
  model?: string
}

interface ToolCall {
  tool: string
  server: string
  arguments: any
  result?: any
}

interface MCPServer {
  name: string
  type?: 'local' | 'remote'
  endpoint?: string
  selected: boolean
  tools?: any[]
  authStatus?: {
    authenticated: boolean
    type: string
    app?: string
    error?: string
  }
}

interface ModelInfo {
  id: string
  name: string
  provider: string
  requires_key: boolean
  is_available: boolean
  supports_tools: boolean
}

interface ApiKeys {
  anthropic?: string
  openai?: string
  mistral?: string
  ollama_host?: string
}

function AppMultiModel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [servers, setServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(false)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [serverFilter, setServerFilter] = useState('')
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  
  // Model selection states
  const [models, setModels] = useState<ModelInfo[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('anthropic/claude-opus-4-1-20250805')
  const [showApiKeyModal, setShowApiKeyModal] = useState(false)
  const [apiKeys, setApiKeys] = useState<ApiKeys>({})
  const [tempApiKeys, setTempApiKeys] = useState<ApiKeys>({})
  // const [showMarketplace, setShowMarketplace] = useState(false) // MCPD removed

  useEffect(() => {
    // Load saved preferences from localStorage
    const savedModel = localStorage.getItem('selectedModel')
    const savedKeys = localStorage.getItem('apiKeys')
    
    if (savedModel) setSelectedModel(savedModel)
    if (savedKeys) {
      const keys = JSON.parse(savedKeys)
      setApiKeys(keys)
      setTempApiKeys(keys)
    }
    
    fetchServers()
    fetchModels()
    connectWebSocket()
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  useEffect(() => {
    if (autoScroll) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, autoScroll])

  const fetchModels = async () => {
    try {
      const response = await axios.get(`${API_BASE}/models`)
      setModels(response.data.models)
    } catch (err) {
      console.error('Failed to fetch models:', err)
    }
  }

  const fetchServers = async () => {
    try {
      const response = await axios.get(`${API_BASE}/servers`)
      console.log('Fetched servers:', response.data)
      
      // Preserve existing selection state when updating servers
      const currentSelections = new Map(servers.map(s => [s.name, s.selected]))
      
      const serverList = response.data.map((server: any) => {
        const serverName = typeof server === 'string' ? server : server.name
        return {
          name: serverName,
          type: server.type || 'local',
          endpoint: server.endpoint,
          // Preserve existing selection, or auto-select Composio servers
          selected: currentSelections.get(serverName) ?? (serverName?.startsWith('composio-') || false),
          tools: []
        }
      })
      console.log('Processed server list with preserved selections:', serverList)
      setServers(serverList)
    } catch (err) {
      console.error('Failed to fetch servers:', err)
      setError('Failed to connect to backend. Make sure it\'s running on port 8000')
    }
  }

  const checkAuthStatus = async (serverName: string) => {
    try {
      const response = await axios.get(`${API_BASE}/servers/${serverName}/auth-status`)
      return response.data
    } catch (err) {
      console.error(`Failed to check auth status for ${serverName}:`, err)
      return null
    }
  }

  const toggleServer = async (serverName: string) => {
    const updatedServers = await Promise.all(
      servers.map(async (server) => {
        if (server.name === serverName) {
          const newSelected = !server.selected
          
          // Check auth status for remote servers
          if (server.type === 'remote' && !server.authStatus) {
            const authStatus = await checkAuthStatus(serverName)
            server.authStatus = authStatus
          }
          
          // For Composio servers, check if authenticated before allowing selection
          if (newSelected && server.authStatus?.type === 'composio' && !server.authStatus.authenticated) {
            setError(`Please authenticate with ${server.authStatus.app} first`)
            return { ...server, selected: false }
          }
          
          if (newSelected && !server.tools?.length) {
            try {
              const response = await axios.get(`${API_BASE}/servers/${serverName}/tools`)
              return { ...server, selected: newSelected, tools: response.data.tools || [] }
            } catch (err) {
              console.error(`Failed to fetch tools for ${serverName}:`, err)
              return { ...server, selected: false }
            }
          }
          return { ...server, selected: newSelected }
        }
        return server
      })
    )
    setServers(updatedServers)
  }

  const connectWebSocket = () => {
    const ws = new WebSocket(`${WS_BASE}/ws/chat`)
    
    ws.onopen = () => {
      setConnected(true)
      setError(null)
      setReconnectAttempt(0)
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      console.log('WebSocket message received:', data)
      
      if (data.type === 'message') {
        console.log('Processing assistant message:', data.content?.substring(0, 100))
        setMessages(prev => [...prev, {
          role: data.role,
          content: data.content,
          timestamp: new Date(),
          model: selectedModel
        }])
        setLoading(false)
      } else if (data.type === 'status') {
        // Could show status messages in UI
        console.log('Status:', data.message)
      } else if (data.type === 'tool_call') {
        setMessages(prev => {
          const lastMessage = prev[prev.length - 1]
          if (lastMessage && lastMessage.role === 'assistant') {
            const toolCall: ToolCall = {
              tool: data.tool,
              server: data.server,
              arguments: data.arguments
            }
            return [
              ...prev.slice(0, -1),
              {
                ...lastMessage,
                toolCalls: [...(lastMessage.toolCalls || []), toolCall]
              }
            ]
          }
          return prev
        })
      } else if (data.type === 'tool_result') {
        setMessages(prev => {
          const lastMessage = prev[prev.length - 1]
          if (lastMessage && lastMessage.toolCalls) {
            const updatedToolCalls = lastMessage.toolCalls.map(tc => 
              tc.tool === data.tool && tc.server === data.server
                ? { ...tc, result: data.result }
                : tc
            )
            return [
              ...prev.slice(0, -1),
              {
                ...lastMessage,
                toolCalls: updatedToolCalls
              }
            ]
          }
          return prev
        })
      } else if (data.type === 'error') {
        setError(data.message)
        setLoading(false)
      }
    }
    
    ws.onclose = () => {
      setConnected(false)
      setReconnectAttempt(prev => prev + 1)
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), 30000)
      setTimeout(() => connectWebSocket(), delay)
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
      setError('WebSocket connection failed')
    }
    
    wsRef.current = ws
  }

  const copyToClipboard = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const clearConversation = () => {
    if (confirm('Are you sure you want to clear the conversation?')) {
      setMessages([])
    }
  }

  const sendMessage = () => {
    if (!input.trim() || !connected) return
    
    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date()
    }
    
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setError(null)
    
    const selectedServers = servers.filter(s => s.selected).map(s => s.name)
    console.log('Current servers state:', servers)
    console.log('Selected servers being sent:', selectedServers)
    
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const payload = {
        messages: [...messages, userMessage].map(m => ({
          role: m.role,
          content: m.content
        })),
        available_servers: selectedServers,
        model: selectedModel,
        api_keys: apiKeys
      }
      console.log('Sending WebSocket payload:', payload)
      wsRef.current.send(JSON.stringify(payload))
    }
  }

  const saveApiKeys = async () => {
    setApiKeys(tempApiKeys)
    localStorage.setItem('apiKeys', JSON.stringify(tempApiKeys))
    
    // Update backend with new keys
    try {
      await axios.post(`${API_BASE}/update-keys`, { keys: tempApiKeys })
      await fetchModels() // Refresh model availability
      setShowApiKeyModal(false)
    } catch (err) {
      console.error('Failed to update keys:', err)
      setError('Failed to update API keys')
    }
  }

  const handleModelChange = (modelId: string) => {
    setSelectedModel(modelId)
    localStorage.setItem('selectedModel', modelId)
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setShowShortcuts(!showShortcuts)
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'l') {
        e.preventDefault()
        clearConversation()
      }
      // Removed global Cmd/Ctrl+Enter handler - now using Enter key in textarea
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [showShortcuts, input, connected, selectedModel])

  const filteredServers = servers.filter(s => 
    s.name.toLowerCase().includes(serverFilter.toLowerCase())
  )

  const estimatedTokens = Math.ceil(input.length / 4)
  const currentModel = models.find(m => m.id === selectedModel)

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Keyboard Shortcuts Modal */}
      {showShortcuts && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center" onClick={() => setShowShortcuts(false)}>
          <div className="bg-white rounded-lg p-6 max-w-md" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Keyboard className="w-5 h-5" />
              Keyboard Shortcuts
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Toggle this help</span>
                <kbd className="px-2 py-1 bg-gray-100 rounded">⌘K</kbd>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Clear conversation</span>
                <kbd className="px-2 py-1 bg-gray-100 rounded">⌘L</kbd>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Send message</span>
                <kbd className="px-2 py-1 bg-gray-100 rounded">Enter</kbd>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">New line in message</span>
                <kbd className="px-2 py-1 bg-gray-100 rounded">Shift+Enter</kbd>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Focus input</span>
                <kbd className="px-2 py-1 bg-gray-100 rounded">⌘/</kbd>
              </div>
            </div>
            <button
              onClick={() => setShowShortcuts(false)}
              className="mt-4 w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Server Marketplace Modal - MCPD removed */}
      {/* {showMarketplace && (
        <ServerMarketplace 
          onClose={() => setShowMarketplace(false)} 
          onServerInstalled={() => fetchServers()}
        />
      )} */}

      {/* API Keys Modal */}
      {showApiKeyModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center" onClick={() => setShowApiKeyModal(false)}>
          <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Key className="w-5 h-5" />
              API Keys Configuration
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Anthropic API Key</label>
                <input
                  type="password"
                  value={tempApiKeys.anthropic || ''}
                  onChange={(e) => setTempApiKeys({...tempApiKeys, anthropic: e.target.value})}
                  placeholder="sk-ant-..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">OpenAI API Key</label>
                <input
                  type="password"
                  value={tempApiKeys.openai || ''}
                  onChange={(e) => setTempApiKeys({...tempApiKeys, openai: e.target.value})}
                  placeholder="sk-..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Mistral API Key</label>
                <input
                  type="password"
                  value={tempApiKeys.mistral || ''}
                  onChange={(e) => setTempApiKeys({...tempApiKeys, mistral: e.target.value})}
                  placeholder="..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Ollama Host (for local models)</label>
                <input
                  type="text"
                  value={tempApiKeys.ollama_host || 'http://localhost:11434'}
                  onChange={(e) => setTempApiKeys({...tempApiKeys, ollama_host: e.target.value})}
                  placeholder="http://localhost:11434"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="mt-6 flex gap-2">
              <button
                onClick={saveApiKeys}
                className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
              >
                Save Keys
              </button>
              <button
                onClick={() => setShowApiKeyModal(false)}
                className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
            <p className="mt-4 text-xs text-gray-500">
              Keys are stored locally in your browser and sent to the backend for model access.
            </p>
          </div>
        </div>
      )}

      {/* Sidebar */}
      <div className="w-96 bg-white border-r border-gray-200 p-4 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Server className="w-5 h-5" />
              MCP Servers
            </h2>
            {currentModel && !currentModel.supports_tools && (
              <p className="text-xs text-amber-600 mt-1">Tools disabled for {currentModel.provider}</p>
            )}
          </div>
          {/* MCPD Registry removed - only remote servers supported */}
          {/* <button
            onClick={() => setShowMarketplace(true)}
            className="px-3 py-1 bg-blue-500 text-white text-sm rounded-lg hover:bg-blue-600 flex items-center gap-1" 
            title="Browse and install MCP servers"
          >
            <Package className="w-4 h-4" />
            Add Server
          </button> */}
        </div>
        
        {/* Composio OAuth Integration */}
        <ComposioOAuthFlow onServerAdded={fetchServers} />
        
        {/* Quick Add Server (Manual URL) */}
        <QuickAddServer onServerAdded={fetchServers} />
        
        {/* Server Filter */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Filter servers..."
            value={serverFilter}
            onChange={(e) => setServerFilter(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
        
        <div className="space-y-2">
          {filteredServers.length === 0 ? (
            <div className="text-gray-500 text-sm">
              {servers.length === 0 ? 'No servers available' : 'No servers match filter'}
            </div>
          ) : (
            filteredServers.map((server) => (
              <div key={server.name} className="border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleServer(server.name)}
                  className={`w-full p-3 text-left hover:bg-gray-50 transition-colors flex items-center justify-between ${
                    server.selected ? 'bg-blue-50' : ''
                  }`}
                  disabled={currentModel && !currentModel.supports_tools}
                >
                  <div className="flex items-center gap-2">
                    {server.type === 'remote' ? (
                      <>
                        <Globe className="w-4 h-4 text-blue-500" title="Remote server" />
                        {server.authStatus?.type === 'composio' && (
                          server.authStatus.authenticated ? (
                            <Unlock className="w-3 h-3 text-green-500" title="Authenticated" />
                          ) : (
                            <Lock className="w-3 h-3 text-amber-500" title="Authentication required" />
                          )
                        )}
                      </>
                    ) : (
                      <HardDrive className="w-4 h-4 text-gray-500" title="Local server" />
                    )}
                    <span className="font-medium">{server.name}</span>
                    {server.authStatus?.app && (
                      <span className="text-xs text-gray-400">({server.authStatus.app})</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {server.tools && server.tools.length > 0 && (
                      <span className="text-xs text-gray-500">
                        {server.tools.length} tool{server.tools.length !== 1 ? 's' : ''} available
                      </span>
                    )}
                    <input
                      type="checkbox"
                      checked={server.selected}
                      onChange={() => {
                        setServers(prev => prev.map(s => 
                          s.name === server.name 
                            ? { ...s, selected: !s.selected }
                            : s
                        ))
                      }}
                      disabled={currentModel && !currentModel.supports_tools}
                      className="w-4 h-4"
                    />
                  </div>
                </button>
                
                {/* Show auth prompt for unauthenticated Composio servers */}
                {server.authStatus?.type === 'composio' && !server.authStatus.authenticated && (
                  <div className="px-3 py-2 bg-amber-50 border-t border-amber-200">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-amber-700 flex items-center gap-1">
                        <Lock className="w-3 h-3" />
                        Authentication required for {server.authStatus.app}
                      </span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={async () => {
                            const newAuthStatus = await checkAuthStatus(server.name)
                            setServers(prev => prev.map(s => 
                              s.name === server.name ? {...s, authStatus: newAuthStatus} : s
                            ))
                          }}
                          className="px-2 py-1 bg-gray-200 text-gray-700 text-xs rounded hover:bg-gray-300 flex items-center gap-1"
                          title="Check authentication status"
                        >
                          <RefreshCw className="w-3 h-3" />
                        </button>
                        <button
                        onClick={async () => {
                          try {
                            const response = await axios.post(`${API_BASE}/servers/${server.name}/initiate-auth`, {})
                            console.log('Auth response:', response.data)
                            
                            // Check for redirect URL in the response
                            const redirectUrl = response.data.data?.response_data?.redirect_url || 
                                              response.data.data?.redirect_url ||
                                              response.data.redirect_url
                            
                            if (redirectUrl) {
                              window.open(redirectUrl, '_blank')
                              setError(`Please complete authentication in the opened window for ${server.authStatus?.app}`)
                              
                              // After a delay, refresh auth status
                              setTimeout(async () => {
                                const newAuthStatus = await checkAuthStatus(server.name)
                                setServers(prev => prev.map(s => 
                                  s.name === server.name ? {...s, authStatus: newAuthStatus} : s
                                ))
                              }, 5000)
                            } else {
                              setError(`Authentication initiated for ${server.authStatus?.app}. ${response.data.data?.response_data?.message || ''}`)
                            }
                          } catch (err: any) {
                            console.error('Auth error:', err)
                            setError(`Failed to initiate authentication: ${err.response?.data?.detail || err.message}`)
                          }
                        }}
                        className="px-2 py-1 bg-amber-600 text-white text-xs rounded hover:bg-amber-700 flex items-center gap-1"
                      >
                        <ExternalLink className="w-3 h-3" />
                        Authenticate
                      </button>
                      </div>
                    </div>
                  </div>
                )}
                
                {server.selected && server.tools && server.tools.length > 0 && (
                  <div className="px-3 pb-3 pt-1 border-t bg-gray-50">
                    <div className="space-y-1">
                      {server.tools.slice(0, 5).map((tool: any) => (
                        <div key={tool.name} className="flex items-start gap-2 py-1">
                          <Wrench className="w-3 h-3 mt-1 text-gray-400" />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-700 truncate">
                              {tool.name}
                            </div>
                          </div>
                        </div>
                      ))}
                      {server.tools.length > 5 && (
                        <div className="text-xs text-gray-500 pl-5">
                          +{server.tools.length - 5} more tools
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
        
        <div className="mt-6 p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center gap-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : reconnectAttempt > 0 ? 'bg-yellow-500' : 'bg-red-500'}`} />
            <span className="text-gray-600">
              {connected ? 'Connected' : reconnectAttempt > 0 ? `Reconnecting... (${reconnectAttempt})` : 'Disconnected'}
            </span>
            {reconnectAttempt > 0 && (
              <RefreshCw className="w-3 h-3 animate-spin text-gray-500" />
            )}
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header Bar */}
        <div className="bg-white border-b border-gray-200 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={clearConversation}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                title="Clear conversation (⌘L)"
              >
                <Trash2 className="w-4 h-4 text-gray-600" />
              </button>
              <span className="text-sm text-gray-500">
                {messages.length} message{messages.length !== 1 ? 's' : ''}
              </span>
            </div>
            
            {/* Model Selector moved to header */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-gray-500" />
                <select
                  value={selectedModel}
                  onChange={(e) => handleModelChange(e.target.value)}
                  className="px-3 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm min-w-[200px]"
                >
                  {models.map(model => (
                    <option 
                      key={model.id} 
                      value={model.id}
                      disabled={!model.is_available}
                    >
                      {model.name} {!model.is_available && '(needs key)'}
                    </option>
                  ))}
                </select>
                {currentModel && !currentModel.is_available && (
                  <button
                    onClick={() => setShowApiKeyModal(true)}
                    className="p-1.5 bg-amber-100 hover:bg-amber-200 rounded-lg transition-colors"
                    title="API key required"
                  >
                    <AlertCircle className="w-4 h-4 text-amber-600" />
                  </button>
                )}
                {currentModel && currentModel.is_available && (
                  <button
                    onClick={() => setShowApiKeyModal(true)}
                    className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Manage API keys"
                  >
                    <Key className="w-4 h-4 text-gray-500" />
                  </button>
                )}
              </div>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowShortcuts(true)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors" 
                  title="Keyboard shortcuts (⌘K)"
                >
                  <Keyboard className="w-4 h-4 text-gray-500" />
                </button>
                
                <button
                  onClick={() => setAutoScroll(!autoScroll)}
                  className={`p-2 rounded-lg transition-colors ${
                    autoScroll ? 'bg-blue-100 text-blue-600' : 'hover:bg-gray-100 text-gray-600'
                  }`}
                  title={autoScroll ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}
                >
                  {autoScroll ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>
        
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Warning if model doesn't support tools but servers are selected */}
          {currentModel && !currentModel.supports_tools && servers.some(s => s.selected) && (
            <div className="mx-auto max-w-2xl mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-medium">{currentModel.name}</span> doesn't support MCP tools. 
                Selected servers won't be available. Switch to a Claude model to use tools.
              </div>
            </div>
          )}
          
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              <div className="text-center">
                <Bot className="w-12 h-12 mx-auto mb-4" />
                <p>Start a conversation with {currentModel?.name || 'your selected model'}</p>
                {currentModel?.supports_tools ? (
                  <p className="text-sm mt-2">Select MCP servers from the sidebar to enable tools</p>
                ) : (
                  <p className="text-sm mt-2 text-amber-600">This model doesn't support MCP tools</p>
                )}
              </div>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={index}
                className={`flex gap-3 ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <div
                  className={`max-w-2xl ${
                    message.role === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-white border border-gray-200'
                  } rounded-lg p-4`}
                >
                  <div className="flex items-start gap-3">
                    {message.role === 'user' ? (
                      <User className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    ) : (
                      <Bot className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1">
                      {message.role === 'assistant' ? (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            code({node, inline, className, children, ...props}) {
                              const match = /language-(\w+)/.exec(className || '')
                              return !inline && match ? (
                                <div className="relative group">
                                  <SyntaxHighlighter
                                    {...props}
                                    style={vscDarkPlus}
                                    language={match[1]}
                                    PreTag="div"
                                  >
                                    {String(children).replace(/\n$/, '')}
                                  </SyntaxHighlighter>
                                  <button
                                    onClick={() => copyToClipboard(String(children), `code-${index}-${match[1]}`)}
                                    className="absolute top-2 right-2 p-1 bg-gray-700 text-white rounded opacity-0 group-hover:opacity-100 transition-opacity"
                                  >
                                    {copiedId === `code-${index}-${match[1]}` ? (
                                      <Check className="w-4 h-4" />
                                    ) : (
                                      <Copy className="w-4 h-4" />
                                    )}
                                  </button>
                                </div>
                              ) : (
                                <code className="bg-gray-100 px-1 py-0.5 rounded text-sm" {...props}>
                                  {children}
                                </code>
                              )
                            }
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      ) : (
                        <div className="whitespace-pre-wrap">{message.content}</div>
                      )}
                      
                      {message.toolCalls && message.toolCalls.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {message.toolCalls.map((toolCall, i) => (
                            <div key={i} className="bg-gray-50 rounded p-2 text-sm">
                              <div className="font-medium text-gray-700 flex items-center gap-2">
                                <Wrench className="w-3 h-3" />
                                {toolCall.server}.{toolCall.tool}
                              </div>
                              <div className="text-xs text-gray-500 mt-1">
                                Args: {JSON.stringify(toolCall.arguments)}
                              </div>
                              {toolCall.result && (
                                <div className="text-xs mt-1 p-1 bg-white rounded relative group">
                                  <div className="flex items-start justify-between">
                                    <span>Result: {JSON.stringify(toolCall.result)}</span>
                                    <button
                                      onClick={() => copyToClipboard(JSON.stringify(toolCall.result, null, 2), `tool-${index}-${i}`)}
                                      className="ml-2 p-1 hover:bg-gray-200 rounded"
                                    >
                                      {copiedId === `tool-${index}-${i}` ? (
                                        <Check className="w-3 h-3 text-green-600" />
                                      ) : (
                                        <Copy className="w-3 h-3 text-gray-500" />
                                      )}
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
          
          {loading && (
            <div className="flex gap-3">
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <Bot className="w-5 h-5" />
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm text-gray-500">
                    {currentModel?.name} is thinking...
                  </span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 p-4 bg-white">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendMessage()
                  }
                }}
                placeholder={`Ask ${currentModel?.name || 'the model'} anything... (Enter to send, Shift+Enter for new line)`}
                disabled={!connected || !currentModel?.is_available}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 resize-none"
                rows={3}
              />
              <div className="absolute bottom-2 right-2 text-xs text-gray-400">
                {input.length} chars • ~{estimatedTokens} tokens
              </div>
            </div>
            <button
              onClick={sendMessage}
              disabled={!connected || !input.trim() || loading || !currentModel?.is_available}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
              Send
            </button>
          </div>
          {!currentModel?.is_available && (
            <p className="mt-2 text-sm text-amber-600">
              ⚠️ Add API key for {currentModel?.provider} to use this model
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default AppMultiModel