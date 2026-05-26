import { useCallback, useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { useStore } from './hooks/useStore'
import { useWebSocket } from './hooks/useWebSocket'
import { useAudioStream } from './hooks/useAudioStream'
import { useWakeWord } from './hooks/useWakeWord'
import { useTTSPlayer } from './hooks/useTTSPlayer'
import HolographicDisplay from './components/HolographicDisplay'
import ParticleField from './components/ParticleField'
import VoiceVisualizer from './components/VoiceVisualizer'
import ChatPanel from './components/ChatPanel'
import Dashboard from './components/Dashboard'
import StatusIndicator from './components/StatusIndicator'
import type { WSMessage } from './types'

export default function App() {
  const { addMessage, setStatus, setVolume, setConnected, setWakeWordActive, wakeWordActive, status } = useStore()
  const recordingRef = useRef(false)
  const { playAudio } = useTTSPlayer()

  const handleWake = useCallback(() => {
    if (recordingRef.current) return
    recordingRef.current = true
    setWakeWordActive(false)
    startRecording()
    setStatus('listening')
  }, [])

  const handleMessage = useCallback((msg: WSMessage) => {
    addMessage(msg)
    if (msg.type === 'transcription') setStatus('processing')
    if (msg.type === 'response') setStatus('speaking')
    if (msg.type === 'idle') {
      stopRecording()
      recordingRef.current = false
      setStatus('idle')
      setWakeWordActive(true)
    }
  }, [addMessage, setStatus, setWakeWordActive])

  const handleAudioBlob = useCallback((blob: Blob) => {
    playAudio(blob)
  }, [playAudio])

  const { sendAudio } = useWebSocket({
    onMessage: handleMessage,
    onAudioData: handleAudioBlob,
    onStatusChange: setConnected,
  })

  const { startRecording, stopRecording } = useAudioStream({
    onAudioData: sendAudio,
    onVolumeChange: setVolume,
  })

  useWakeWord({
    onWake: handleWake,
    enabled: wakeWordActive && status === 'idle',
  })

  const toggleListening = useCallback(() => {
    if (status === 'idle') {
      recordingRef.current = true
      setWakeWordActive(false)
      startRecording()
      setStatus('listening')
    } else {
      stopRecording()
      recordingRef.current = false
      setStatus('idle')
      setWakeWordActive(true)
    }
  }, [status, startRecording, stopRecording, setStatus, setWakeWordActive])

  return (
    <>
      <div className="scan-line" />
      <div className="vignette" />

      <Canvas camera={{ position: [0, 0, 12], fov: 60 }}>
        <ParticleField />
        <HolographicDisplay />
        <VoiceVisualizer />
      </Canvas>

      <Dashboard />
      <ChatPanel />
      <StatusIndicator onToggle={toggleListening} />
    </>
  )
}
