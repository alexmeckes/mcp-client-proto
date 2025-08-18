import { useState } from 'react'
import { Plus, Loader2, Check, AlertCircle, Sparkles } from 'lucide-react'
import axios from 'axios'
import { API_BASE } from './config'

interface QuickAddServersProps {
  onServerAdded: () => void
}

export default function QuickAddServers({ onServerAdded }: QuickAddServersProps) {
  const [customerId, setCustomerId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)

  const handleAddDemo = async () => {
    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      // Add a demo Composio server that doesn't require authentication
      // This could be a public demo endpoint if Composio provides one
      const response = await axios.post(`${API_BASE}/add-remote-server`, {
        input: 'https://mcp.composio.dev/demo/mcp'
      })

      if (response.data.error) {
        setError(response.data.error)
      } else {
        setSuccess('Demo server added! Try asking about GitHub repos or sending a Slack message.')
        onServerAdded()
        setTimeout(() => setSuccess(null), 5000)
      }
    } catch (err: any) {
      // If demo endpoint doesn't exist, show helpful message
      setError('Demo server not available. Enter your Composio Customer ID below to connect your own tools.')
    } finally {
      setLoading(false)
    }
  }

  const handleQuickAdd = async () => {
    if (!customerId.trim()) {
      setError('Please enter your Customer ID')
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      // Add multiple popular services at once
      const services = ['github', 'slack', 'notion']
      const promises = services.map(service => 
        axios.post(`${API_BASE}/add-remote-server`, {
          input: `https://mcp.composio.dev/${service}/mcp?customerId=${customerId.trim()}`
        })
      )

      await Promise.all(promises)
      setSuccess(`Added ${services.length} services! You can now use GitHub, Slack, and Notion tools.`)
      setCustomerId('')
      onServerAdded()
      setTimeout(() => setSuccess(null), 5000)
    } catch (err: any) {
      setError('Failed to add services. Check your Customer ID and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mb-6 space-y-3">
      {/* Try Demo Button */}
      <div className="p-4 bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg border border-purple-200">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 font-medium text-purple-900">
              <Sparkles className="w-4 h-4" />
              Try MCP Tools - No Setup Required!
            </div>
            <p className="text-xs text-purple-700 mt-1">
              Test drive MCP with a demo server
            </p>
          </div>
          <button
            onClick={handleAddDemo}
            disabled={loading}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-300 flex items-center gap-2 text-sm"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Adding...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" />
                Try Demo
              </>
            )}
          </button>
        </div>
      </div>

      {/* Quick Add Your Own */}
      <div className="p-4 bg-white rounded-lg border border-gray-200">
        <div className="flex items-center justify-between gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Add Your Own Tools
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleQuickAdd()}
                placeholder="Enter Composio Customer ID"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
              <button
                onClick={handleQuickAdd}
                disabled={loading || !customerId.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 flex items-center gap-2 text-sm"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                Add Tools
              </button>
            </div>
            <button
              onClick={() => setShowHelp(!showHelp)}
              className="text-xs text-blue-600 hover:underline mt-2"
            >
              {showHelp ? 'Hide' : 'What\'s a Customer ID?'}
            </button>
          </div>
        </div>

        {showHelp && (
          <div className="mt-3 p-3 bg-blue-50 rounded text-xs text-blue-800">
            <p className="mb-2">
              A Customer ID connects your Composio account to enable tool integrations.
            </p>
            <p>
              <strong>Get yours:</strong> Sign up at{' '}
              <a 
                href="https://app.composio.dev" 
                target="_blank" 
                rel="noopener noreferrer"
                className="underline"
              >
                composio.dev
              </a>
              {' '}→ Copy your Customer ID → Paste it above
            </p>
          </div>
        )}
      </div>

      {/* Success/Error Messages */}
      {success && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 flex items-start gap-2">
          <Check className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}