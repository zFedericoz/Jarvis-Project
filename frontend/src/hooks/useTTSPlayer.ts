import { useRef, useCallback } from 'react'

export function useTTSPlayer() {
  const audioContext = useRef<AudioContext | null>(null)

  const playAudio = useCallback(async (blob: Blob) => {
    try {
      const arrayBuffer = await blob.arrayBuffer()
      audioContext.current = new AudioContext()
      const audioBuffer = await audioContext.current.decodeAudioData(arrayBuffer)
      const source = audioContext.current.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioContext.current.destination)
      source.start()
    } catch (err) {
      console.error('TTS playback error:', err)
    }
  }, [])

  const stopAudio = useCallback(() => {
    audioContext.current?.close()
    audioContext.current = null
  }, [])

  return { playAudio, stopAudio }
}
