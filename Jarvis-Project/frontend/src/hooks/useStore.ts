import { create } from 'zustand'
import type { AppStatus, WSMessage } from '../types'

interface AppStore {
  status: AppStatus
  messages: WSMessage[]
  volume: number
  connected: boolean
  wakeWordActive: boolean
  wakeSupported: boolean
  setStatus: (status: AppStatus) => void
  addMessage: (msg: WSMessage) => void
  setVolume: (vol: number) => void
  setConnected: (c: boolean) => void
  setWakeWordActive: (a: boolean) => void
  setWakeSupported: (s: boolean) => void
  clearMessages: () => void
}

export const useStore = create<AppStore>((set) => ({
  status: 'idle',
  messages: [],
  volume: 0,
  connected: false,
  wakeWordActive: true,
  wakeSupported: true,

  setStatus: (status) => set({ status }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages.slice(-50), msg] })),
  setVolume: (volume) => set({ volume }),
  setConnected: (connected) => set({ connected }),
  setWakeWordActive: (wakeWordActive) => set({ wakeWordActive }),
  setWakeSupported: (wakeSupported) => set({ wakeSupported }),
  clearMessages: () => set({ messages: [] }),
}))
