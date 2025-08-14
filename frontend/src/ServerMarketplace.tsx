import { useState, useEffect } from 'react'
import { Package, Download, Trash2, Settings, RefreshCw, Check, X, AlertCircle, Search, Filter, Loader2, ChevronRight } from 'lucide-react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

interface ServerInfo {
  name: string
  package: string
  description: string
  category: string
  required_env: string[]
  required_args: string[]
  example_args: string[]
  installed: boolean
}

interface ServerMarketplaceProps {
  onClose: () => void
  onServerInstalled: () => void
}

export default function ServerMarketplace({ onClose, onServerInstalled }: ServerMarketplaceProps) {
  const [servers, setServers] = useState<ServerInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [installing, setInstalling] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('All')
  const [expandedServer, setExpandedServer] = useState<string | null>(null)
  const [serverConfigs, setServerConfigs] = useState<Record<string, { args: string[], env: Record<string, string> }>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchRegistry()
  }, [])

  const fetchRegistry = async () => {
    try {
      setLoading(true)
      const response = await axios.get(`${API_BASE}/mcp-registry`)
      setServers(response.data)
      
      // Initialize configs for servers with requirements
      const configs: Record<string, { args: string[], env: Record<string, string> }> = {}
      response.data.forEach((server: ServerInfo) => {
        configs[server.name] = {
          args: server.example_args || [],
          env: server.required_env.reduce((acc, key) => ({ ...acc, [key]: '' }), {})
        }
      })
      setServerConfigs(configs)
    } catch (err) {
      console.error('Failed to fetch registry:', err)
      setError('Failed to load server registry')
    } finally {
      setLoading(false)
    }
  }

  const installServer = async (server: ServerInfo) => {
    setInstalling(server.name)
    setError(null)
    
    try {
      const config = serverConfigs[server.name]
      
      // Validate required fields
      for (const envKey of server.required_env) {
        if (!config.env[envKey]) {
          setError(`Please provide ${envKey}`)
          setInstalling(null)
          return
        }
      }
      
      for (let i = 0; i < server.required_args.length; i++) {
        if (!config.args[i]) {
          setError(`Please provide ${server.required_args[i]}`)
          setInstalling(null)
          return
        }
      }
      
      // Install the server
      await axios.post(`${API_BASE}/install-mcp-server`, {
        name: server.name,
        package: server.package,
        args: config.args.filter(Boolean),
        env: config.env
      })
      
      // Restart mcpd to pick up changes
      await axios.post(`${API_BASE}/restart-mcpd`)
      
      // Refresh the list
      await fetchRegistry()
      onServerInstalled()
      
    } catch (err: any) {
      console.error('Failed to install server:', err)
      setError(err.response?.data?.detail || 'Failed to install server')
    } finally {
      setInstalling(null)
    }
  }

  const uninstallServer = async (serverName: string) => {
    if (!confirm(`Are you sure you want to uninstall ${serverName}?`)) return
    
    setInstalling(serverName)
    setError(null)
    
    try {
      await axios.post(`${API_BASE}/uninstall-mcp-server/${serverName}`)
      await axios.post(`${API_BASE}/restart-mcpd`)
      await fetchRegistry()
      onServerInstalled()
    } catch (err: any) {
      console.error('Failed to uninstall server:', err)
      setError(err.response?.data?.detail || 'Failed to uninstall server')
    } finally {
      setInstalling(null)
    }
  }

  const updateConfig = (serverName: string, field: 'args' | 'env', key: string | number, value: string) => {
    setServerConfigs(prev => ({
      ...prev,
      [serverName]: {
        ...prev[serverName],
        [field]: field === 'args' 
          ? prev[serverName].args.map((v, i) => i === key ? value : v)
          : { ...prev[serverName].env, [key]: value }
      }
    }))
  }

  const categories = ['All', ...new Set(servers.map(s => s.category))]
  
  const filteredServers = servers.filter(server => {
    const matchesSearch = server.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         server.description.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesCategory = selectedCategory === 'All' || server.category === selectedCategory
    return matchesSearch && matchesCategory
  })

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold flex items-center gap-2">
              <Package className="w-6 h-6" />
              MCP Server Marketplace
            </h2>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          {/* Search and Filter */}
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search servers..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Server List */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
            </div>
          ) : filteredServers.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              No servers found matching your criteria
            </div>
          ) : (
            <div className="space-y-3">
              {filteredServers.map(server => (
                <div key={server.name} className="border rounded-lg overflow-hidden">
                  <div 
                    className="p-4 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setExpandedServer(expandedServer === server.name ? null : server.name)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-lg">{server.name}</h3>
                          {server.installed && (
                            <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full flex items-center gap-1">
                              <Check className="w-3 h-3" />
                              Installed
                            </span>
                          )}
                          <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
                            {server.category}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mt-1">{server.description}</p>
                        {(server.required_env.length > 0 || server.required_args.length > 0) && (
                          <div className="flex gap-4 mt-2 text-xs text-gray-500">
                            {server.required_env.length > 0 && (
                              <span>Requires: {server.required_env.join(', ')}</span>
                            )}
                            {server.required_args.length > 0 && (
                              <span>Args: {server.required_args.join(', ')}</span>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <ChevronRight className={`w-4 h-4 text-gray-400 transition-transform ${expandedServer === server.name ? 'rotate-90' : ''}`} />
                      </div>
                    </div>
                  </div>
                  
                  {/* Expanded Configuration */}
                  {expandedServer === server.name && (
                    <div className="px-4 pb-4 border-t bg-gray-50">
                      <div className="mt-4 space-y-3">
                        {/* Environment Variables */}
                        {server.required_env.length > 0 && (
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              Environment Variables
                            </label>
                            <div className="space-y-2">
                              {server.required_env.map(envKey => (
                                <div key={envKey} className="flex items-center gap-2">
                                  <label className="w-40 text-sm text-gray-600">{envKey}:</label>
                                  <input
                                    type="password"
                                    value={serverConfigs[server.name]?.env[envKey] || ''}
                                    onChange={(e) => updateConfig(server.name, 'env', envKey, e.target.value)}
                                    placeholder="Enter value..."
                                    className="flex-1 px-3 py-1 border border-gray-300 rounded"
                                    disabled={server.installed}
                                  />
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {/* Arguments */}
                        {server.required_args.length > 0 && (
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              Arguments
                            </label>
                            <div className="space-y-2">
                              {server.required_args.map((arg, index) => (
                                <div key={index} className="flex items-center gap-2">
                                  <label className="w-40 text-sm text-gray-600">{arg}:</label>
                                  <input
                                    type="text"
                                    value={serverConfigs[server.name]?.args[index] || ''}
                                    onChange={(e) => updateConfig(server.name, 'args', index, e.target.value)}
                                    placeholder={server.example_args[index] || 'Enter value...'}
                                    className="flex-1 px-3 py-1 border border-gray-300 rounded"
                                    disabled={server.installed}
                                  />
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {/* Package Info */}
                        <div className="text-xs text-gray-500">
                          Package: <code className="bg-gray-100 px-1 py-0.5 rounded">{server.package}</code>
                        </div>
                        
                        {/* Action Buttons */}
                        <div className="flex justify-end gap-2 pt-2">
                          {server.installed ? (
                            <button
                              onClick={() => uninstallServer(server.name)}
                              disabled={installing === server.name}
                              className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:bg-gray-300 flex items-center gap-2"
                            >
                              {installing === server.name ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Trash2 className="w-4 h-4" />
                              )}
                              Uninstall
                            </button>
                          ) : (
                            <button
                              onClick={() => installServer(server)}
                              disabled={installing === server.name}
                              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 flex items-center gap-2"
                            >
                              {installing === server.name ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Download className="w-4 h-4" />
                              )}
                              Install
                            </button>
                          )}
                        </div>
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
  )
}