import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useStore } from '../hooks/useStore'
import { PARTICLES } from '../utils/constants'

export default function ParticleField() {
  const mesh = useRef<THREE.Points>(null!)
  const volume = useStore((s) => s.volume)

  const [positions, velocities, origins, phases] = useMemo(() => {
    const count = PARTICLES.count
    const pos = new Float32Array(count * 3)
    const vel = new Float32Array(count * 3)
    const org = new Float32Array(count * 3)
    const phs = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      const i3 = i * 3
      pos[i3] = (Math.random() - 0.5) * 20
      pos[i3 + 1] = (Math.random() - 0.5) * 20
      pos[i3 + 2] = (Math.random() - 0.5) * 10 - 5
      org[i3] = pos[i3]
      org[i3 + 1] = pos[i3 + 1]
      org[i3 + 2] = pos[i3 + 2]
      vel[i3] = (Math.random() - 0.5) * PARTICLES.speed
      vel[i3 + 1] = (Math.random() - 0.5) * PARTICLES.speed
      vel[i3 + 2] = (Math.random() - 0.5) * PARTICLES.speed * 0.5
      phs[i] = Math.random() * Math.PI * 2
    }
    return [pos, vel, org, phs]
  }, [])

  const energyRef = useRef(0)

  useFrame((state, delta) => {
    const time = state.clock.elapsedTime
    const positionsAttr = mesh.current.geometry.attributes.position
    const pos = positionsAttr.array as Float32Array

    const energyTarget = Math.min(volume * 2, 1)
    const lerpSpeed = 3
    const dt = Math.min(lerpSpeed * delta, 1)
    const energy = energyRef.current + (energyTarget - energyRef.current) * dt
    energyRef.current = energy

    for (let i = 0; i < PARTICLES.count; i++) {
      const i3 = i * 3

      const waveSpeed = 0.002 + energy * 0.008
      pos[i3] += Math.sin(time * 0.2 + phases[i]) * waveSpeed
      pos[i3 + 1] += Math.cos(time * 0.15 + phases[i]) * waveSpeed
      pos[i3 + 2] += Math.sin(time * 0.1 + phases[i] * 0.7) * waveSpeed * 0.5

      const dx = pos[i3] - origins[i3]
      const dy = pos[i3 + 1] - origins[i3 + 1]
      const dz = pos[i3 + 2] - origins[i3 + 2]
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.001
      const pushStrength = energy * 0.015

      pos[i3] += (dx / dist) * pushStrength
      pos[i3 + 1] += (dy / dist) * pushStrength
      pos[i3 + 2] += (dz / dist) * pushStrength * 0.5

      const maxRadius = 10 + energy * 4
      if (Math.abs(pos[i3]) > maxRadius) pos[i3] *= -0.9
      if (Math.abs(pos[i3 + 1]) > maxRadius) pos[i3 + 1] *= -0.9
      if (Math.abs(pos[i3 + 2]) > 12) pos[i3 + 2] *= -0.9
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
