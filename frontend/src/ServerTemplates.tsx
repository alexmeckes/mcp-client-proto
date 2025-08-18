import { useState } from 'react'
import { Github, Database, MessageSquare, Mail, Calendar, FileText, AlertCircle, ExternalLink, Loader2, Check } from 'lucide-react'
import axios from 'axios'
import { API_BASE } from './config'

interface ServerTemplate {
  name: string
  provider: string
  service: string
  urlTemplate: string
  icon: React.ReactNode
  description: string
  setupUrl: string
  requiresCustomerId: boolean
}

const SERVER_TEMPLATES: ServerTemplate[] = [
  {
    name: 'GitHub',
    provider: 'Composio',
    service: 'github',
    urlTemplate: 'https://mcp.composio.dev/github/mcp?customerId={CUSTOMER_ID}',
    icon: <Github className="w-5 h-5" />,
    description: 'Repository management, issues, PRs, and more',
    setupUrl: 'https://composio.dev',
    requiresCustomerId: true
  },
  {
    name: 'Supabase',
    provider: 'Composio',
    service: 'supabase',
    urlTemplate: 'https://mcp.composio.dev/supabase/mcp?customerId={CUSTOMER_ID}',
    icon: <Database className="w-5 h-5" />,
    description: 'Database operations and real-time subscriptions',
    setupUrl: 'https://composio.dev',
    requiresCustomerId: true
  },
  {
    name: 'Slack',
    provider: 'Composio',
    service: 'slack',
    urlTemplate: 'https://mcp.composio.dev/slack/mcp?customerId={CUSTOMER_ID}',
    icon: <MessageSquare className="w-5 h-5" />,
    description: 'Send messages, manage channels, and more',
    setupUrl: 'https://composio.dev',
    requiresCustomerId: true
  },
  {
    name: 'Gmail',
    provider: 'Composio',
    service: 'gmail',
    urlTemplate: 'https://mcp.composio.dev/gmail/mcp?customerId={CUSTOMER_ID}',
    icon: <Mail className="w-5 h-5" />,
    description: 'Send emails, manage inbox, and attachments',
    setupUrl: 'https://composio.dev',
    requiresCustomerId: true
  },
  {
    name: 'Google Calendar',
    provider: 'Composio',
    service: 'googlecalendar',
    urlTemplate: 'https://mcp.composio.dev/googlecalendar/mcp?customerId={CUSTOMER_ID}',
    icon: <Calendar className="w-5 h-5" />,
    description: 'Create events, manage calendars, and reminders',
    setupUrl: 'https://composio.dev',
    requiresCustomerId: true
  },
  {
    name: 'Notion',
    provider: 'Composio',
    service: 'notion',
    urlTemplate: 'https://mcp.composio.dev/notion/mcp?customerId={CUSTOMER_ID}',
    icon: <FileText className="w-5 h-5" />,
    description: 'Create pages, manage databases, and workspaces',
    setupUrl: 'https://composio.dev',
    requiresCustomerId: true
  }
]

interface ServerTemplatesProps {
  onServerAdded: () => void
}

export default function ServerTemplates({ onServerAdded }: ServerTemplatesProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<ServerTemplate | null>(null)
  const [customerId, setCustomerId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const handleAddServer = async (template: ServerTemplate) => {
    if (template.requiresCustomerId && !customerId.trim()) {
      setError('Please enter your Composio Customer ID')
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const url = template.urlTemplate.replace('{CUSTOMER_ID}', customerId.trim())
      
      const response = await axios.post(`${API_BASE}/add-remote-server`, {
        input: url
      })

      if (response.data.error) {
        setError(response.data.error)
      } else {
        setSuccess(`✓ ${template.name} server added successfully!`)
        setSelectedTemplate(null)
        setCustomerId('')
        onServerAdded()
        
        // Clear success message after 3 seconds
        setTimeout(() => setSuccess(null), 3000)
      }
    } catch (err: any) {
      setError(err.response?.data?.error || `Failed to add ${template.name} server`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <span className="text-blue-500">⚡</span> Quick Add Popular Services
      </h3>
      
      {/* Template Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-4">
        {SERVER_TEMPLATES.map((template) => (
          <button
            key={template.service}
            onClick={() => setSelectedTemplate(template)}
            className="p-3 border border-gray-200 rounded-lg hover:border-blue-400 hover:bg-blue-50 transition-all text-left group"
          >
            <div className="flex items-start gap-2">
              <div className="text-gray-600 group-hover:text-blue-600 mt-0.5">
                {template.icon}
              </div>
              <div className="flex-1">
                <div className="font-medium text-sm text-gray-900">{template.name}</div>
                <div className="text-xs text-gray-500 mt-0.5">{template.provider}</div>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Setup Modal */}
      {selectedTemplate && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center" onClick={() => setSelectedTemplate(null)}>
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-start gap-3 mb-4">
              <div className="text-blue-600">{selectedTemplate.icon}</div>
              <div>
                <h3 className="text-lg font-semibold">Add {selectedTemplate.name} Server</h3>
                <p className="text-sm text-gray-600 mt-1">{selectedTemplate.description}</p>
              </div>
            </div>

            {selectedTemplate.requiresCustomerId && (
              <>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Composio Customer ID
                  </label>
                  <input
                    type="text"
                    value={customerId}
                    onChange={(e) => setCustomerId(e.target.value)}
                    placeholder="Enter your Customer ID"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    autoFocus
                  />
                  <div className="mt-2 text-xs text-gray-500">
                    Don't have a Customer ID? 
                    <a 
                      href={selectedTemplate.setupUrl} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="ml-1 text-blue-600 hover:underline inline-flex items-center gap-1"
                    >
                      Get one at Composio
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>

                {/* Preview URL */}
                {customerId && (
                  <div className="mb-4 p-2 bg-gray-50 rounded text-xs font-mono text-gray-600 break-all">
                    {selectedTemplate.urlTemplate.replace('{CUSTOMER_ID}', customerId)}
                  </div>
                )}
              </>
            )}

            {/* Error/Success Messages */}
            {error && (
              <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div className="mb-4 p-2 bg-green-50 border border-green-200 rounded text-sm text-green-700 flex items-start gap-2">
                <Check className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{success}</span>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-2">
              <button
                onClick={() => handleAddServer(selectedTemplate)}
                disabled={loading || (selectedTemplate.requiresCustomerId && !customerId.trim())}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    Add Server
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setSelectedTemplate(null)
                  setCustomerId('')
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