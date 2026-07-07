import { create } from 'zustand'
import type { AppStatus, WSMessage } from '../types'

export interface ChatSession {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
  last_message_preview: string | null
}

interface ChatMessage {
  id: number
  session_id: number
  role: string
  content: string
  intent: string
  created_at: string
}

interface AppStore {
  status: AppStatus
  messages: WSMessage[]
  volume: number
  connected: boolean
  wakeWordActive: boolean
  wakeSupported: boolean
  sessions: ChatSession[]
  activeSessionId: number | null
  chatHistory: ChatMessage[]

  setStatus: (status: AppStatus) => void
  addMessage: (msg: WSMessage) => void
  setVolume: (vol: number) => void
  setConnected: (c: boolean) => void
  setWakeWordActive: (a: boolean) => void
  setWakeSupported: (s: boolean) => void
  clearMessages: () => void
  setSessions: (sessions: ChatSession[]) => void
  setActiveSessionId: (id: number | null) => void
  addSession: (session: ChatSession) => void
  removeSession: (id: number) => void
  updateSession: (id: number, updates: Partial<ChatSession>) => void
  setChatHistory: (messages: ChatMessage[]) => void
  addChatHistory: (msg: ChatMessage) => void
}

export const useStore = create<AppStore>((set) => ({
  status: 'idle',
  messages: [],
  volume: 0,
  connected: false,
  wakeWordActive: true,
  wakeSupported: true,
  sessions: [],
  activeSessionId: null,
  chatHistory: [],

  setStatus: (status) => set({ status }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages.slice(-50), msg] })),
  setVolume: (volume) => set({ volume }),
  setConnected: (connected) => set({ connected }),
  setWakeWordActive: (wakeWordActive) => set({ wakeWordActive }),
  setWakeSupported: (wakeSupported) => set({ wakeSupported }),
  clearMessages: () => set({ messages: [] }),
  setSessions: (sessions) => set({ sessions }),
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  addSession: (session) => set((s) => ({ sessions: [session, ...s.sessions] })),
  removeSession: (id) => set((s) => ({ sessions: s.sessions.filter((x) => x.id !== id), activeSessionId: s.activeSessionId === id ? null : s.activeSessionId })),
  updateSession: (id, updates) => set((s) => ({ sessions: s.sessions.map((x) => x.id === id ? { ...x, ...updates } : x) })),
  setChatHistory: (chatHistory) => set({ chatHistory }),
  addChatHistory: (msg) => set((s) => ({ chatHistory: [...s.chatHistory, msg] })),
}))
