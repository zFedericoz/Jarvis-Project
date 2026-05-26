import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useStore } from '../hooks/useStore'
import { JARVIS_COLORS } from '../utils/constants'

const BAR_COUNT = 32
const BAR_SPACING = 0.15
const TOTAL_WIDTH = BAR_COUNT * BAR_SPACING

export default function VoiceVisualizer() {
  const mesh = useRef<THREE.InstancedMesh>(null!)
  const volume = useStore((s) => s.volume)
  const status = useStore((s) => s.status)

  const dummy = useRef(new THREE.Object3D())

  useFrame((state) => {
    if (!mesh.current) return
    const t = state.clock.elapsedTime
    const isActive = status === 'listening' || status === 'speaking'

    for (let i = 0; i < BAR_COUNT; i++) {
      const x = (i - BAR_COUNT / 2) * BAR_SPACING
      const noise = Math.sin(t * 3 + i * 0.5) * 0.2 + Math.sin(t * 5 + i * 0.3) * 0.1
      const volFactor = isActive ? volume : 0.05
      const height = Math.max(0.02, volFactor * 2 + noise * 0.3)

      dummy.current.position.set(x, height / 2 - 4.5, -2)
      dummy.current.scale.set(0.06, height, 0.06)
      dummy.current.updateMatrix()
      mesh.current.setMatrixAt(i, dummy.current.matrix)
    }
    mesh.current.instanceMatrix.needsUpdate = true
  })

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, BAR_COUNT]}>
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial
        color={JARVIS_COLORS.primary}
        transparent
        opacity={0.4}
        blending={THREE.AdditiveBlending}
      />
    </instancedMesh>
  )
}
