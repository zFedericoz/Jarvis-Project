import { useRef, useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../hooks/useStore'
import { JARVIS_COLORS, API_URL } from '../utils/constants'
import type { WSMessage } from '../types'

function FeedbackButtons({ userMsg, assistantMsg, language, intent }: {
  userMsg: string; assistantMsg: string; language?: string; intent?: string
}) {
  const [sent, setSent] = useState<'up' | 'down' | null>(null)

  const sendFeedback = useCallback(async (rating: number) => {
    if (sent) return
    try {
      await fetch(`${API_URL}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_message: userMsg,
          assistant_response: assistantMsg,
          rating,
          language: language || 'it',
          intent: intent || 'chat',
        }),
      })
      setSent(rating === 2 ? 'up' : 'down')
    } catch { /* ignore */ }
  }, [userMsg, assistantMsg, language, intent, sent])

  return (
    <div style={{ display: 'flex', gap: 6, marginTop: 4, opacity: sent ? 0.4 : 0.6 }}>
      <span
        onClick={() => sendFeedback(2)}
        style={{
          cursor: sent ? 'default' : 'pointer',
          fontSize: 12,
          color: sent === 'up' ? JARVIS_COLORS.success : JARVIS_COLORS.textDim,
          transition: 'color 0.2s',
        }}
        title="Buona risposta"
      >👍</span>
      <span
        onClick={() => sendFeedback(1)}
        style={{
          cursor: sent ? 'default' : 'pointer',
          fontSize: 12,
          color: sent === 'down' ? JARVIS_COLORS.error : JARVIS_COLORS.textDim,
          transition: 'color 0.2s',
        }}
        title="Risposta non utile"
      >👎</span>
    </div>
  )
}

export default function ChatPanel() {
  const messages = useStore((s) => s.messages)
  const addMessage = useStore((s) => s.addMessage)
  const bottomRef = useRef<HTMLDivElement>(null!)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState<{ name: string; content: string }[]>([])
  const inputRef = useRef<HTMLInputElement>(null!)
  const fileInputRef = useRef<HTMLInputElement>(null!)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return
    const newFiles: { name: string; content: string }[] = []
    for (const file of Array.from(files)) {
      const content = await file.text()
      newFiles.push({ name: file.name, content })
    }
    setAttachedFiles((prev) => [...prev, ...newFiles])
    e.target.value = ''
  }

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSend = async () => {
    const msg = text.trim()
    if ((!msg && attachedFiles.length === 0) || sending) return

    let fullText = msg
    const files = [...attachedFiles]
    if (files.length > 0) {
      const fileBlocks = files.map((f) => `=== FILE: ${f.name} ===\n${f.content}`)
      fullText = msg ? `${msg}\n\n${fileBlocks.join('\n\n')}` : fileBlocks.join('\n\n')
    }

    setText('')
    setAttachedFiles([])
    setSending(true)

    addMessage({ type: 'transcription', text: msg || `[${files.length} file allegati]`, language: 'it' })

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: fullText }),
      })
      const data = await res.json()

      addMessage({
        type: 'response',
        text: data.response,
        language: data.language || 'it',
        intent: data.intent,
      })

      if (data.audio) {
        const binary = atob(data.audio)
        const bytes = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
        const blob = new Blob([bytes], { type: 'audio/wav' })
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        await audio.play()
      }
    } catch {
      addMessage({ type: 'error', text: 'Errore di comunicazione con il server.' })
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const getLastUserText = (currentIndex: number): string => {
    for (let i = currentIndex - 1; i >= 0; i--) {
      const txt = messages[i].text
      if (messages[i].type === 'transcription' && txt) return txt
    }
    return ''
  }

  return (
    <div style={{
      position: 'fixed',
      bottom: 100,
      right: 24,
      width: 420,
      maxHeight: 420,
      display: 'flex',
      flexDirection: 'column',
      zIndex: 100,
      background: JARVIS_COLORS.surface,
      border: `1px solid ${JARVIS_COLORS.primary}33`,
      borderRadius: 8,
      padding: 12,
      backdropFilter: 'blur(10px)',
    }}>
      <div style={{ flex: 1, overflowY: 'auto', marginBottom: 8 }}>
        <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              style={{
                marginBottom: 8,
                padding: '6px 10px',
                borderRadius: 4,
                borderLeft: `2px solid ${
                  msg.type === 'transcription' ? JARVIS_COLORS.warning : JARVIS_COLORS.primary
                }`,
                fontSize: 13,
                color: msg.type === 'transcription' ? JARVIS_COLORS.warning : JARVIS_COLORS.text,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              <div style={{ fontSize: 10, opacity: 0.5, marginBottom: 2 }}>
                {msg.type === 'transcription' ? 'YOU' : msg.type === 'error' ? 'ERROR' : 'JARVIS'} · {(msg.language || 'it').toUpperCase()}
              </div>
              {msg.text}
              {msg.intent && msg.type === 'response' && (
                <div style={{ fontSize: 9, opacity: 0.4, marginTop: 4 }}>
                  intent: {msg.intent}
                </div>
              )}
              {msg.type === 'response' && msg.text && (
                <FeedbackButtons
                  userMsg={getLastUserText(i)}
                  assistantMsg={msg.text}
                  language={msg.language}
                  intent={msg.intent}
                />
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {attachedFiles.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
          {attachedFiles.map((f, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '2px 8px', borderRadius: 4,
              background: `${JARVIS_COLORS.primary}22`,
              border: `1px solid ${JARVIS_COLORS.primary}44`,
              fontSize: 11, color: JARVIS_COLORS.primary,
            }}>
              <span style={{ maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {f.name}
              </span>
              <span
                onClick={() => removeFile(i)}
                style={{ cursor: 'pointer', opacity: 0.6, marginLeft: 4 }}
              >
                ✕
              </span>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 6 }}>
        <label style={{
          padding: '6px 10px',
          borderRadius: 4,
          border: `1px solid ${JARVIS_COLORS.primary}44`,
          background: 'rgba(0,0,0,0.3)',
          color: JARVIS_COLORS.primary,
          fontSize: 13,
          cursor: 'pointer',
          fontFamily: "'Share Tech Mono', monospace",
          display: 'flex',
          alignItems: 'center',
        }}>
          📎
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </label>
        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={attachedFiles.length > 0 ? "Scrivi cosa fare con i file..." : "Scrivi un messaggio..."}
          disabled={sending}
          style={{
            flex: 1,
            padding: '6px 10px',
            borderRadius: 4,
            border: `1px solid ${JARVIS_COLORS.primary}44`,
            background: 'rgba(0,0,0,0.3)',
            color: JARVIS_COLORS.text,
            fontSize: 13,
            fontFamily: "'Share Tech Mono', monospace",
            outline: 'none',
          }}
        />
        <button
          onClick={handleSend}
          disabled={sending || (!text.trim() && attachedFiles.length === 0)}
          style={{
            padding: '6px 14px',
            borderRadius: 4,
            border: `1px solid ${JARVIS_COLORS.primary}`,
            background: `${JARVIS_COLORS.primary}22`,
            color: JARVIS_COLORS.primary,
            fontSize: 13,
            cursor: 'pointer',
            fontFamily: "'Share Tech Mono', monospace",
          }}
        >
          {sending ? '...' : 'INVIA'}
        </button>
      </div>
    </div>
  )
}