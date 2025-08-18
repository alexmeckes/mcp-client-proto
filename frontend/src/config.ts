// API Configuration
export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
export const WS_BASE = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'

// Feature flags
export const ENABLE_LOCAL_MCPD = import.meta.env.VITE_ENABLE_LOCAL_MCPD === 'true'