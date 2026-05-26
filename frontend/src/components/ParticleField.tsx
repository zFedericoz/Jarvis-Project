import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { PARTICLES } from '../utils/constants'

export default function ParticleField() {
  const mesh = useRef<THREE.Points>(null!)

  const [positions, velocities] = useMemo(() => {
    const pos = new Float32Array(PARTICLES.count * 3)
    const vel = new Float32Array(PARTICLES.count * 3)
    for (let i = 0; i < PARTICLES.count; i++) {
      const i3 = i * 3
      pos[i3] = (Math.random() - 0.5) * 20
      pos[i3 + 1] = (Math.random() - 0.5) * 20
      pos[i3 + 2] = (Math.random() - 0.5) * 10 - 5
      vel[i3] = (Math.random() - 0.5) * PARTICLES.speed
      vel[i3 + 1] = (Math.random() - 0.5) * PARTICLES.speed
      vel[i3 + 2] = (Math.random() - 0.5) * PARTICLES.speed * 0.5
    }
    return [pos, vel]
  }, [])

  useFrame((state) => {
    const time = state.clock.elapsedTime
    const positionsAttr = mesh.current.geometry.attributes.position
    const pos = positionsAttr.array as Float32Array

    for (let i = 0; i < PARTICLES.count; i++) {
      const i3 = i * 3
      pos[i3] += Math.sin(time * 0.2 + i * 0.01) * 0.002
      pos[i3 + 1] += Math.cos(time * 0.15 + i * 0.01) * 0.002
      pos[i3 + 2] += Math.sin(time * 0.1 + i * 0.02) * 0.001

      if (Math.abs(pos[i3]) > 10) pos[i3] *= -0.9
      if (Math.abs(pos[i3 + 1]) > 10) pos[i3 + 1] *= -0.9
    }
    positionsAttr.needsUpdate = true
    mesh.current.rotation.y = time * 0.02
  })

  return (
    <points ref={mesh}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={PARTICLES.count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={PARTICLES.size}
        color={PARTICLES.color}
        transparent
        opacity={0.6}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        sizeAttenuation
      />
    </points>
  )
}
