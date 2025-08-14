import { useState } from 'react'
import { Plus, Loader2, AlertCircle, Info, Zap, Globe, Package, HelpCircle, Check } from 'lucide-react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

interface QuickAddServerProps {
  onServerAdded: () => void
}

export default function QuickAddServer({ onServerAdded }: QuickAddServerProps) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await axios.post(`${API_BASE}/quick-add-server`, {
        input: input.trim(),
        env: {},  // Could add UI for env vars if needed
        args: []  // Could add UI for args if needed
      })

      setSuccess(response.data.message)
      setInput('')
      onServerAdded()
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000)

      // Restart mcpd if it's a local server
      if (response.data.type === 'local') {
        await axios.post(`${API_BASE}/restart-mcpd`)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add server')
    } finally {
      setLoading(false)
    }
  }

  const getPlaceholder = () => {
    const examples = [
      'https://mcp.composio.dev/supabase/mcp?customerId=...',
      '@modelcontextprotocol/server-github',
      'npm:@modelcontextprotocol/server-sqlite',
      'filesystem',
      'time'
    ]
    return examples[Math.floor(Math.random() * examples.length)]
  }

  return (
    <div className="mb-4">
      <form onSubmit={handleSubmit} className="relative">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Zap className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={getPlaceholder()}
              disabled={loading}
              className="w-full pl-9 pr-10 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
            />
            <button
              type="button"
              onClick={() => setShowHelp(!showHelp)}
              className="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 hover:bg-gray-100 rounded"
            >
              <HelpCircle className="w-4 h-4 text-gray-400" />
            </button>
          </div>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:bg-gray-300 flex items-center gap-2 text-sm"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            Quick Add
          </button>
        </div>
      </form>

      {/* Help Dropdown */}
      {showHelp && (
        <div className="mt-2 p-3 bg-gray-50 rounded-lg text-xs">
          <div className="font-semibold mb-2 flex items-center gap-1">
            <Info className="w-3 h-3" />
            Supported Formats:
          </div>
          <div className="space-y-1 text-gray-600">
            <div className="flex items-start gap-2">
              <Globe className="w-3 h-3 mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-medium">Remote URL:</span> https://api.example.com/mcp
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Package className="w-3 h-3 mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-medium">NPM Package:</span> @org/package or npm:package-name
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Package className="w-3 h-3 mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-medium">Registry Name:</span> filesystem, github, sqlite
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Status Messages */}
      {error && (
        <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
      
      {success && (
        <div className="mt-2 p-2 bg-green-50 border border-green-200 rounded text-sm text-green-700 flex items-start gap-2">
          <Check className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}
    </div>
  )
}