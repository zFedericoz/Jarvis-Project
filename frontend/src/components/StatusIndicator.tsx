import { motion } from 'framer-motion'
import { useStore } from '../hooks/useStore'
import { JARVIS_COLORS } from '../utils/constants'

interface Props {
  onToggle: () => void
}

const STATUS_LABELS = {
  idle: 'TAP OR SAY "JARVIS"',
  listening: 'LISTENING...',
  processing: 'PROCESSING...',
  speaking: 'SPEAKING...',
}

const STATUS_COLORS = {
  idle: JARVIS_COLORS.primary,
  listening: JARVIS_COLORS.success,
  processing: JARVIS_COLORS.warning,
  speaking: JARVIS_COLORS.accent,
}

export default function StatusIndicator({ onToggle }: Props) {
  const status = useStore((s) => s.status)
  const volume = useStore((s) => s.volume)
  const wakeWordActive = useStore((s) => s.wakeWordActive)

  return (
    <div style={{
      position: 'fixed',
      bottom: 40,
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 100,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 12,
    }}>
      <motion.button
        onClick={onToggle}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        style={{
          width: 80,
          height: 80,
          borderRadius: '50%',
          border: `2px solid ${STATUS_COLORS[status]}`,
          background: `${STATUS_COLORS[status]}15`,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backdropFilter: 'blur(10px)',
          position: 'relative',
        }}
      >
        <motion.div
          animate={{
            scale: status === 'listening' ? [1, 1.3, 1] : 1,
            opacity: status === 'idle' && wakeWordActive ? [0.4, 1, 0.4] : 1,
          }}
          transition={{
            repeat: status === 'listening' || (status === 'idle' && wakeWordActive) ? Infinity : 0,
            duration: 1.5,
          }}
          style={{
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: STATUS_COLORS[status],
            boxShadow: `0 0 20px ${STATUS_COLORS[status]}, 0 0 40px ${STATUS_COLORS[status]}40`,
          }}
        />

        {status === 'idle' && wakeWordActive && (
          <svg style={{ position: 'absolute', width: '100%', height: '100%' }}>
            {[0, 1].map((i) => (
              <motion.circle
                key={i}
                cx="50%"
                cy="50%"
                r={26 + i * 12}
                fill="none"
                stroke={JARVIS_COLORS.primary}
                strokeWidth={0.3}
                opacity={0.15}
                initial={{ scale: 0.8, opacity: 0.3 }}
                animate={{ scale: 1.3, opacity: 0 }}
                transition={{
                  repeat: Infinity,
                  duration: 2.5,
                  delay: i * 1.2,
                  ease: 'easeOut',
                }}
              />
            ))}
          </svg>
        )}

        {status === 'listening' && (
          <svg style={{ position: 'absolute', width: '100%', height: '100%' }}>
            {[0, 1, 2, 3].map((i) => (
              <motion.circle
                key={i}
                cx="50%"
                cy="50%"
                r={28 + i * 8}
                fill="none"
                stroke={STATUS_COLORS[status]}
                strokeWidth={0.5}
                opacity={0.2}
                initial={{ scale: 0.8, opacity: 0.4 }}
                animate={{ scale: 1.2, opacity: 0 }}
                transition={{
                  repeat: Infinity,
                  duration: 2,
                  delay: i * 0.4,
                  ease: 'easeOut',
                }}
              />
            ))}
          </svg>
        )}
      </motion.button>

      <motion.div
        animate={{ opacity: status === 'idle' ? 0.6 : 1 }}
        style={{
          fontSize: 11,
          letterSpacing: 2,
          color: STATUS_COLORS[status],
          fontFamily: "'Share Tech Mono', monospace",
        }}
      >
        {STATUS_LABELS[status]}
      </motion.div>
    </div>
  )
}
