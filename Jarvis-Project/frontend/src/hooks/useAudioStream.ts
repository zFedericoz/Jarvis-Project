import { useRef, useCallback } from 'react'

interface UseAudioStreamProps {
  onAudioData: (data: ArrayBuffer) => void
  onVolumeChange?: (volume: number) => void
}

export function useAudioStream({ onAudioData, onVolumeChange }: UseAudioStreamProps) {
  const stream = useRef<MediaStream | null>(null)
  const audioCtx = useRef<AudioContext | null>(null)
  const processor = useRef<ScriptProcessorNode | null>(null)
  const source = useRef<MediaStreamAudioSourceNode | null>(null)
  const analyser = useRef<AnalyserNode | null>(null)
  const animationId = useRef<number>()
  const audioBuffer = useRef<Int16Array>(new Int16Array(0))

  const startRecording = useCallback(async () => {
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })

      audioCtx.current = new AudioContext()
      source.current = audioCtx.current.createMediaStreamSource(stream.current)

      analyser.current = audioCtx.current.createAnalyser()
      analyser.current.fftSize = 256
      source.current.connect(analyser.current)

      processor.current = audioCtx.current.createScriptProcessor(4096, 1, 1)
      source.current.connect(processor.current)
      processor.current.connect(audioCtx.current.destination)

      processor.current.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0)
        const pcm = new Int16Array(input.length)
        for (let i = 0; i < input.length; i++) {
          pcm[i] = Math.max(-32768, Math.min(32767, input[i] * 32768))
        }

        audioBuffer.current = Int16Array.from([...audioBuffer.current, ...pcm])

        const threshold = 16000
        if (audioBuffer.current.length >= threshold) {
          const chunk = audioBuffer.current.slice(0, threshold)
          audioBuffer.current = audioBuffer.current.slice(threshold)
          onAudioData(chunk.buffer)
        }
      }

      const analyze = () => {
        if (!analyser.current) return
        const data = new Uint8Array(analyser.current.frequencyBinCount)
        analyser.current.getByteFrequencyData(data)
        const avg = data.reduce((a, b) => a + b, 0) / data.length
        onVolumeChange?.(avg / 255)
        animationId.current = requestAnimationFrame(analyze)
      }
      analyze()
    } catch (err) {
      console.error('Microphone error:', err)
    }
  }, [onAudioData, onVolumeChange])

  const stopRecording = useCallback(() => {
    processor.current?.disconnect()
    source.current?.disconnect()
    analyser.current?.disconnect()
    audioCtx.current?.close()
    stream.current?.getTracks().forEach((t) => t.stop())
    cancelAnimationFrame(animationId.current!)
    audioBuffer.current = new Int16Array(0)
    processor.current = null
    source.current = null
    analyser.current = null
    audioCtx.current = null
    stream.current = null
  }, [])

  return { startRecording, stopRecording }
}
