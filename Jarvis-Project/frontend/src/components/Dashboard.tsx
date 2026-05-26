import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { JARVIS_COLORS } from '../utils/constants'
import { useStore } from '../hooks/useStore'

export default function Dashboard() {
  const [time, setTime] = useState(new Date())
  const connected = useStore((s) => s.connected)

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div style={{
      position: 'fixed',
      top: 24,
      left: 24,
      zIndex: 100,
      color: JARVIS_COLORS.text,
      fontFamily: "'Share Tech Mono', monospace",
    }}>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ fontSize: 11, letterSpacing: 2, opacity: 0.6, marginBottom: 4 }}
      >
        J.A.R.V.I.S. v2.0.0
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        style={{ fontSize: 42, fontWeight: 700, fontFamily: "'Orbitron', sans-serif" }}
      >
        {time.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })}
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        style={{ fontSize: 12, opacity: 0.5, marginTop: 2 }}
      >
        {time.toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}
      >
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: connected ? JARVIS_COLORS.success : JARVIS_COLORS.error,
          boxShadow: `0 0 6px ${connected ? JARVIS_COLORS.success : JARVIS_COLORS.error}`,
        }} />
        {connected ? 'SYSTEM ONLINE' : 'CONNECTING...'}
      </motion.div>
    </div>
  )
}
