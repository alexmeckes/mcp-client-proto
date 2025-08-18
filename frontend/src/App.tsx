import { useState, useEffect, useRef } from 'react'
import { Send, Server, Wrench, Bot, User, Loader2, AlertCircle, Settings, Save, Plus, X, Copy, Check, Trash2, Search, Keyboard, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { API_BASE, WS_BASE } from './config'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  toolCalls?: ToolCall[]
}

interface ToolCall {
  tool: string
  server: string
  arguments: any
  result?: any
}

interface MCPServer {
  name: string
  selected: boolean
  tools?: any[]
}

interface ServerRequiredConfig {
  name: string
  package?: string
  tools: string[]
  required_env: string[]
  required_args: string[]
  required_args_bool: string[]
}

interface ServerRuntimeConfig {
  name: string
  env: Record<string, string>
  args: string[]
}

interface ServerConfigDetail {
  required: ServerRequiredConfig
  runtime: ServerRuntimeConfig
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [servers, setServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(false)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [openConfig, setOpenConfig] = useState<string | null>(null)
  const [serverConfigs, setServerConfigs] = useState<Record<string, ServerConfigDetail>>({})
  const [envDrafts, setEnvDrafts] = useState<Record<string, Record<string, string>>>({})
  const [savingEnv, setSavingEnv] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [serverFilter, setServerFilter] = useState('')
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    fetchServers()
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

  const fetchServers = async () => {
    try {
      const response = await axios.get(`${API_BASE}/servers`)
      // Handle both string array and object array formats
      const serverList = response.data.map((server: string | { name: string, type: string }) => ({
        name: typeof server === 'string' ? server : server.name,
        selected: false,
        tools: []
      }))
      setServers(serverList)
    } catch (err) {
      console.error('Failed to fetch servers:', err)
      setError('Failed to connect to mcpd. Make sure it\'s running on port 8090')
    }
  }

  const toggleServer = async (serverName: string) => {
    const updatedServers = await Promise.all(
      servers.map(async (server) => {
        if (server.name === serverName) {
          const newSelected = !server.selected
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

  const fetchServerConfig = async (serverName: string) => {
    try {
      const res = await axios.get<ServerConfigDetail>(`${API_BASE}/config/server/${serverName}`)
      setServerConfigs(prev => ({ ...prev, [serverName]: res.data }))

      // Initialize env draft with required keys first (prefill with existing), then include existing extras
      const required = res.data.required.required_env || []
      const currentEnv = res.data.runtime.env || {}
      const draft: Record<string, string> = {}
      required.forEach(k => { draft[k] = currentEnv[k] ?? '' })
      Object.keys(currentEnv).forEach(k => { if (!(k in draft)) draft[k] = currentEnv[k] })
      setEnvDrafts(prev => ({ ...prev, [serverName]: draft }))
    } catch (e) {
      console.error('Failed to fetch server config', e)
      setError(`Failed to fetch config for ${serverName}`)
    }
  }

  const openServerConfig = async (serverName: string) => {
    setError(null)
    setOpenConfig(prev => (prev === serverName ? null : serverName))
    if (!serverConfigs[serverName]) {
      await fetchServerConfig(serverName)
    }
  }

  const updateEnvDraft = (serverName: string, key: string, value: string) => {
    setEnvDrafts(prev => ({
      ...prev,
      [serverName]: { ...(prev[serverName] || {}), [key]: value }
    }))
  }

  const addEnvKey = (serverName: string) => {
    const key = ''
    setEnvDrafts(prev => ({ ...prev, [serverName]: { ...(prev[serverName] || {}), [key]: '' } }))
  }

  const removeEnvKey = (serverName: string, key: string) => {
    setEnvDrafts(prev => {
      const next = { ...(prev[serverName] || {}) }
      delete next[key]
      return { ...prev, [serverName]: next }
    })
  }

  const saveEnv = async (serverName: string) => {
    const env = envDrafts[serverName] || {}
    // Filter out empty keys
    const cleaned: Record<string, string> = {}
    Object.keys(env).forEach(k => {
      const key = k.trim()
      if (key) cleaned[key] = env[k]
    })
    setSavingEnv(serverName)
    try {
      await axios.post(`${API_BASE}/config/env`, { server: serverName, env: cleaned })
      await fetchServerConfig(serverName) // refresh
    } catch (e) {
      console.error('Failed to save env', e)
      setError(`Failed to save env for ${serverName}`)
    } finally {
      setSavingEnv(null)
    }
  }

  const connectWebSocket = () => {
    const ws = new WebSocket(`${WS_BASE}/ws/chat`)
    
    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      if (data.type === 'message') {
        setMessages(prev => [...prev, {
          role: data.role,
          content: data.content,
          timestamp: new Date()
        }])
        setLoading(false)
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
    
    ws.onopen = () => {
      setConnected(true)
      setError(null)
      setReconnectAttempt(0)
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
    
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        messages: [...messages, userMessage].map(m => ({
          role: m.role,
          content: m.content
        })),
        available_servers: selectedServers
      }))
    }
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
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault()
        sendMessage()
      }
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [showShortcuts, input, connected])

  const filteredServers = servers.filter(s => 
    s.name.toLowerCase().includes(serverFilter.toLowerCase())
  )

  const estimatedTokens = Math.ceil(input.length / 4)

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
                <kbd className="px-2 py-1 bg-gray-100 rounded">⌘Enter</kbd>
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

      {/* Sidebar */}
      <div className="w-96 bg-white border-r border-gray-200 p-4 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Server className="w-5 h-5" />
            MCP Servers
          </h2>
          <button
            onClick={() => setShowShortcuts(true)}
            className="p-1 hover:bg-gray-100 rounded" 
            title="Keyboard shortcuts (⌘K)"
          >
            <Keyboard className="w-4 h-4 text-gray-500" />
          </button>
        </div>
        
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
                >
                  <span className="font-medium">{server.name}</span>
                  <div className="flex items-center gap-2">
                    {server.tools && server.tools.length > 0 && (
                      <span className="text-xs text-gray-500">
                        {server.tools.length} tools
                      </span>
                    )}
                    <input
                      type="checkbox"
                      checked={server.selected}
                      onChange={() => {}}
                      className="w-4 h-4"
                    />
                  </div>
                </button>
                {/* Config toggle */}
                <div className="flex items-center justify-between px-3 py-2 border-t bg-white">
                  <button
                    onClick={() => openServerConfig(server.name)}
                    className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-2"
                  >
                    <Settings className="w-4 h-4" /> Configure
                  </button>
                  {openConfig === server.name && (
                    <span className="text-xs text-gray-500">Edit env and save. Restart mcpd to apply.</span>
                  )}
                </div>
                
                {server.selected && server.tools && server.tools.length > 0 && (
                  <div className="px-3 pb-3 pt-1 border-t bg-gray-50">
                    <div className="space-y-1">
                      {server.tools.map((tool: any) => (
                        <div key={tool.name} className="flex items-start gap-2 py-1">
                          <Wrench className="w-3 h-3 mt-1 text-gray-400" />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-700 truncate">
                              {tool.name}
                            </div>
                            {tool.description && (
                              <div className="text-xs text-gray-500 line-clamp-2">
                                {tool.description}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Config panel */}
                {openConfig === server.name && (
                  <div className="px-3 pb-3 pt-3 border-t bg-gray-50">
                    {serverConfigs[server.name] ? (
                      <div className="space-y-3">
                        {/* Required keys list */}
                        {serverConfigs[server.name].required.required_env.length > 0 && (
                          <div>
                            <div className="text-xs font-medium text-gray-600 mb-1">Required env</div>
                            <div className="space-y-2">
                              {serverConfigs[server.name].required.required_env.map((k) => (
                                <div key={k} className="flex items-center gap-2">
                                  <label className="w-48 text-xs text-gray-600">{k}</label>
                                  <input
                                    type="text"
                                    value={(envDrafts[server.name]?.[k] ?? '')}
                                    onChange={(e) => updateEnvDraft(server.name, k, e.target.value)}
                                    className="flex-1 px-2 py-1 border border-gray-300 rounded"
                                  />
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Additional env vars */}
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <div className="text-xs font-medium text-gray-600">Additional env</div>
                            <button onClick={() => addEnvKey(server.name)} className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1">
                              <Plus className="w-3 h-3" /> Add
                            </button>
                          </div>
                          <div className="space-y-2">
                            {Object.entries(envDrafts[server.name] || {})
                              .filter(([k]) => !serverConfigs[server.name].required.required_env.includes(k))
                              .map(([k, v], idx) => (
                                <div key={`${k}-${idx}`} className="flex items-center gap-2">
                                  <input
                                    type="text"
                                    value={k}
                                    onChange={(e) => {
                                      const newKey = e.target.value
                                      setEnvDrafts(prev => {
                                        const current = { ...(prev[server.name] || {}) }
                                        const val = current[k]
                                        delete current[k]
                                        current[newKey] = val
                                        return { ...prev, [server.name]: current }
                                      })
                                    }}
                                    placeholder="KEY"
                                    className="w-48 px-2 py-1 border border-gray-300 rounded"
                                  />
                                  <input
                                    type="text"
                                    value={v}
                                    onChange={(e) => updateEnvDraft(server.name, k, e.target.value)}
                                    placeholder="VALUE"
                                    className="flex-1 px-2 py-1 border border-gray-300 rounded"
                                  />
                                  <button onClick={() => removeEnvKey(server.name, k)} className="text-gray-500 hover:text-red-600">
                                    <X className="w-4 h-4" />
                                  </button>
                                </div>
                              ))}
                          </div>
                        </div>

                        {/* Save */}
                        <div className="flex justify-end">
                          <button
                            onClick={() => saveEnv(server.name)}
                            disabled={savingEnv === server.name}
                            className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm flex items-center gap-2 disabled:opacity-60"
                          >
                            {savingEnv === server.name ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            Save env
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-sm text-gray-500">Loading config...</div>
                    )}
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
        <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
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
          <div className="flex items-center gap-2">
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
        
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              <div className="text-center">
                <Bot className="w-12 h-12 mx-auto mb-4" />
                <p>Start a conversation with Claude</p>
                <p className="text-sm mt-2">Select MCP servers from the sidebar to enable tools</p>
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
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault()
                    sendMessage()
                  }
                }}
                placeholder="Type your message... (⌘Enter to send)"
                disabled={!connected}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 resize-none"
                rows={3}
              />
              <div className="absolute bottom-2 right-2 text-xs text-gray-400">
                {input.length} chars • ~{estimatedTokens} tokens
              </div>
            </div>
            <button
              onClick={sendMessage}
              disabled={!connected || !input.trim() || loading}
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
        </div>
      </div>
    </div>
  )
}

export default App