import { useState } from 'react'
import { Plus, Loader2, AlertCircle, HelpCircle, Check, Link } from 'lucide-react'
import axios from 'axios'
import { API_BASE } from './config'

interface QuickAddServerProps {
  onServerAdded: () => void
}

export default function QuickAddServer({ onServerAdded }: QuickAddServerProps) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await axios.post(`${API_BASE}/add-remote-server`, {
        input: input.trim()
      })

      setSuccess(response.data.message || 'Server added successfully!')
      setInput('')
      onServerAdded()
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add server')
    } finally {
      setLoading(false)
    }
  }

  // Collapsed view - just a button
  if (!isExpanded) {
    return (
      <div className="mb-4">
        <button
          onClick={() => setIsExpanded(true)}
          className="w-full p-3 border-2 border-dashed border-gray-300 rounded-lg hover:border-gray-400 hover:bg-gray-50 transition-all group"
        >
          <div className="flex items-center justify-center gap-2 text-gray-600">
            <Link className="w-4 h-4" />
            <span className="text-sm font-medium">Add Custom MCP Server</span>
            <Plus className="w-4 h-4 opacity-50" />
          </div>
        </button>
      </div>
    )
  }

  // Expanded view - full form
  return (
    <div className="mb-4 p-4 bg-white rounded-lg border border-gray-200">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Link className="w-5 h-5 text-gray-600" />
          <h3 className="font-medium text-gray-900">Add Custom MCP Server</h3>
        </div>
        <button
          onClick={() => setIsExpanded(false)}
          className="text-gray-400 hover:text-gray-600"
        >
          <Plus className="w-4 h-4 rotate-45" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter MCP server URL or npm package..."
            disabled={loading}
            className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 text-sm"
          />
          <button
            type="button"
            onClick={() => setShowHelp(!showHelp)}
            className="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
          >
            <HelpCircle className="w-4 h-4" />
          </button>
        </div>

        {showHelp && (
          <div className="p-3 bg-blue-50 rounded-lg text-xs text-blue-900">
            <p className="font-medium mb-2">Supported formats:</p>
            <ul className="space-y-1 ml-4 list-disc">
              <li><code className="bg-white px-1 py-0.5 rounded">https://...</code> - Remote MCP server URL</li>
              <li><code className="bg-white px-1 py-0.5 rounded">npm:package-name</code> - NPM package</li>
              <li><code className="bg-white px-1 py-0.5 rounded">npx:package-name</code> - NPX command</li>
            </ul>
            <p className="mt-2">
              Example: <code className="bg-white px-1 py-0.5 rounded text-[11px]">npm:@modelcontextprotocol/server-filesystem</code>
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="w-full px-3 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2 text-sm"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Adding Server...
            </>
          ) : (
            <>
              <Plus className="w-4 h-4" />
              Add Server
            </>
          )}
        </button>
      </form>

      {success && (
        <div className="mt-3 p-2 bg-green-50 border border-green-200 rounded text-sm text-green-700 flex items-center gap-2">
          <Check className="w-4 h-4 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {error && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}