export interface WSMessage {
  type: 'transcription' | 'response' | 'status' | 'error' | 'idle' | 'speaking_start' | 'speaking_end' | 'wake'
  text?: string
  language?: string
  intent?: string
  status?: string
}

export interface ActionModule {
  name: string
  icon: string
  description: string
  enabled: boolean
}

export interface SystemMetric {
  label: string
  value: string | number
  unit?: string
  trend?: 'up' | 'down' | 'stable'
}

export type AppStatus = 'idle' | 'listening' | 'processing' | 'speaking'
