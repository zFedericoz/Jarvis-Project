import { useRef, useCallback } from 'react'

export function useTTSPlayer() {
  const audioContext = useRef<AudioContext | null>(null)

  const getContext = useCallback(() => {
    if (!audioContext.current || audioContext.current.state === 'closed') {
      audioContext.current = new AudioContext()
    }
    return audioContext.current
  }, [])

  const playAudio = useCallback(async (blob: Blob) => {
    try {
      const arrayBuffer = await blob.arrayBuffer()
      const ctx = getContext()
      const audioBuffer = await ctx.decodeAudioData(arrayBuffer)
      const source = ctx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(ctx.destination)
      source.start()
    } catch (err) {
      console.error('TTS playback error:', err)
    }
  }, [getContext])

  const stopAudio = useCallback(() => {
    audioContext.current?.close()
    audioContext.current = null
  }, [])

  return { playAudio, stopAudio }
}