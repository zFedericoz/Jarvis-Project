import { useEffect, useRef, useCallback } from 'react'

const WAKE_WS_URL = `ws://${location.hostname}/api/ws/wake`

interface UseWakeWordProps {
  onWake: () => void
  enabled: boolean
}

export function useWakeWord({ onWake, enabled }: UseWakeWordProps) {
  const ws = useRef<WebSocket | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const audioCtx = useRef<AudioContext | null>(null)
  const processor = useRef<ScriptProcessorNode | null>(null)
  const source = useRef<MediaStreamAudioSourceNode | null>(null)

  const connect = useCallback(async () => {
    if (!enabled) return

    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })

      audioCtx.current = new AudioContext({ sampleRate: 16000 })
      source.current = audioCtx.current.createMediaStreamSource(stream.current)
      processor.current = audioCtx.current.createScriptProcessor(512, 1, 1)

      ws.current = new WebSocket(WAKE_WS_URL)

      ws.current.onopen = () => {
        source.current!.connect(processor.current!)
        processor.current!.connect(audioCtx.current!.destination)

        processor.current!.onaudioprocess = (e) => {
          if (ws.current?.readyState !== WebSocket.OPEN) return
          const input = e.inputBuffer.getChannelData(0)
          const pcm = new Int16Array(input.length)
          for (let i = 0; i < input.length; i++) {
            pcm[i] = Math.max(-32768, Math.min(32767, input[i] * 32768))
          }
          ws.current.send(pcm.buffer)
        }
      }

      ws.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'wake') {
            cleanup()
            onWake()
          }
        } catch {}
      }

      ws.current.onclose = () => {
        setTimeout(connect, 2000)
      }
    } catch (err) {
      console.error('Wake word mic error:', err)
    }
  }, [enabled, onWake])

  const cleanup = useCallback(() => {
    processor.current?.disconnect()
    source.current?.disconnect()
    audioCtx.current?.close()
    stream.current?.getTracks().forEach((t) => t.stop())
    ws.current?.close()
    processor.current = null
    source.current = null
    audioCtx.current = null
    stream.current = null
    ws.current = null
  }, [])

  useEffect(() => {
    if (enabled) {
      connect()
    } else {
      cleanup()
    }
    return cleanup
  }, [enabled, connect, cleanup])

  return { cleanup }
}
