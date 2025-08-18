import { useState } from 'react'
import { Zap, Plus, Loader2, Check, AlertCircle, HelpCircle, ExternalLink } from 'lucide-react'
import axios from 'axios'
import { API_BASE } from './config'

interface SimpleComposioConnectProps {
  onServerAdded: () => void
}

const POPULAR_TOOLS = [
  { id: 'github', name: 'GitHub', description: 'Repos, PRs, Issues' },
  { id: 'slack', name: 'Slack', description: 'Messages, Channels' },
  { id: 'notion', name: 'Notion', description: 'Pages, Databases' },
  { id: 'gmail', name: 'Gmail', description: 'Email, Drafts' },
  { id: 'linear', name: 'Linear', description: 'Issues, Projects' },
  { id: 'jira', name: 'Jira', description: 'Tickets, Boards' },
]

export default function SimpleComposioConnect({ onServerAdded }: SimpleComposioConnectProps) {
  const [customerId, setCustomerId] = useState('')
  const [loading, setLoading] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const [addedTools, setAddedTools] = useState<Set<string>>(new Set())

  const handleAddTool = async (toolId: string, toolName: string) => {
    if (!customerId.trim()) {
      setError('Please enter your Composio Customer ID first')
      return
    }

    setLoading(toolId)
    setError(null)
    setSuccess(null)

    try {
      const url = `https://mcp.composio.dev/${toolId}/mcp?customerId=${customerId.trim()}`
      
      const response = await axios.post(`${API_BASE}/add-remote-server`, {
        input: url
      })

      if (response.data.error) {
        setError(response.data.error)
      } else {
        setAddedTools(prev => new Set([...prev, toolId]))
        setSuccess(`✓ ${toolName} connected successfully!`)
        onServerAdded()
        setTimeout(() => setSuccess(null), 3000)
      }
    } catch (err: any) {
      setError(`Failed to add ${toolName}. Check your Customer ID.`)
    } finally {
      setLoading(null)
    }
  }

  const handleAddAll = async () => {
    if (!customerId.trim()) {
      setError('Please enter your Composio Customer ID first')
      return
    }

    setLoading('all')
    setError(null)
    setSuccess(null)

    try {
      const promises = POPULAR_TOOLS.map(tool => 
        axios.post(`${API_BASE}/add-remote-server`, {
          input: `https://mcp.composio.dev/${tool.id}/mcp?customerId=${customerId.trim()}`
        })
      )

      await Promise.all(promises)
      setAddedTools(new Set(POPULAR_TOOLS.map(t => t.id)))
      setSuccess(`✓ All ${POPULAR_TOOLS.length} tools connected!`)
      onServerAdded()
      setTimeout(() => setSuccess(null), 5000)
    } catch (err: any) {
      setError('Failed to add some tools. Check your Customer ID.')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="mb-6 space-y-3">
      {/* Customer ID Input */}
      <div className="p-4 bg-white rounded-lg border border-gray-200">
        <div className="flex items-start gap-3">
          <Zap className="w-5 h-5 text-yellow-500 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-medium text-gray-900 mb-2">Connect Composio Tools</h3>
            
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                placeholder="Enter your Composio Customer ID"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
              <button
                onClick={() => setShowHelp(!showHelp)}
                className="p-2 text-gray-500 hover:text-gray-700"
              >
                <HelpCircle className="w-5 h-5" />
              </button>
            </div>

            {showHelp && (
              <div className="mb-3 p-3 bg-blue-50 rounded-lg text-xs">
                <p className="text-blue-900 font-medium mb-1">How to get your Customer ID:</p>
                <ol className="list-decimal list-inside space-y-1 text-blue-800">
                  <li>Go to <a href="https://app.composio.dev" target="_blank" rel="noopener noreferrer" className="underline">app.composio.dev</a></li>
                  <li>Sign up or log in to your account</li>
                  <li>Find your Customer ID in the dashboard</li>
                  <li>Copy and paste it above</li>
                </ol>
                <p className="mt-2 text-blue-700">
                  This ID lets you use your own Composio integrations securely.
                </p>
              </div>
            )}

            {/* Quick Actions */}
            {customerId && (
              <div className="flex gap-2 mb-3">
                <button
                  onClick={handleAddAll}
                  disabled={loading === 'all'}
                  className="px-3 py-1.5 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg hover:from-blue-600 hover:to-purple-700 disabled:opacity-50 text-sm font-medium flex items-center gap-2"
                >
                  {loading === 'all' ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Adding All...
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" />
                      Add All Tools
                    </>
                  )}
                </button>
                <a
                  href="https://app.composio.dev"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm flex items-center gap-2"
                >
                  Manage Integrations
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            )}

            {/* Tool Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {POPULAR_TOOLS.map((tool) => {
                const isAdded = addedTools.has(tool.id)
                return (
                  <button
                    key={tool.id}
                    onClick={() => handleAddTool(tool.id, tool.name)}
                    disabled={!customerId || loading === tool.id || isAdded}
                    className={`p-2 rounded-lg border text-left transition-all text-sm ${
                      isAdded 
                        ? 'bg-green-50 border-green-300 cursor-default'
                        : 'border-gray-200 hover:border-blue-400 hover:bg-blue-50 disabled:opacity-50 disabled:hover:bg-white disabled:hover:border-gray-200'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">{tool.name}</div>
                        <div className="text-xs text-gray-500">{tool.description}</div>
                      </div>
                      {loading === tool.id ? (
                        <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                      ) : isAdded ? (
                        <Check className="w-4 h-4 text-green-600" />
                      ) : (
                        <Plus className="w-4 h-4 text-gray-400" />
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      {success && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 flex items-center gap-2">
          <Check className="w-4 h-4 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}