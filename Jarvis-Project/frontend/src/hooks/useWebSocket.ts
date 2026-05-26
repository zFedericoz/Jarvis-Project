import { useEffect, useRef, useCallback } from 'react'
import { WS_URL } from '../utils/constants'
import type { WSMessage } from '../types'

interface UseWebSocketProps {
  onMessage: (msg: WSMessage) => void
  onAudioData?: (audioBlob: Blob) => void
  onStatusChange?: (connected: boolean) => void
}

export function useWebSocket({ onMessage, onAudioData, onStatusChange }: UseWebSocketProps) {
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimeout = useRef<number>()

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    const socket = new WebSocket(WS_URL)

    socket.binaryType = 'blob'

    socket.onopen = () => {
      onStatusChange?.(true)
    }

    socket.onmessage = (event) => {
      if (event.data instanceof Blob) {
        onAudioData?.(event.data)
      } else {
        try {
          const msg: WSMessage = JSON.parse(event.data)
          onMessage(msg)
        } catch {
          console.warn('Unknown message:', event.data)
        }
      }
    }

    socket.onclose = () => {
      onStatusChange?.(false)
      reconnectTimeout.current = window.setTimeout(connect, 2000)
    }

    socket.onerror = () => {
      socket.close()
    }

    ws.current = socket
  }, [onMessage, onAudioData, onStatusChange])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimeout.current)
      ws.current?.close()
    }
  }, [connect])

  const sendAudio = useCallback((audioData: ArrayBuffer) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(audioData)
    }
  }, [])

  return { sendAudio }
}
