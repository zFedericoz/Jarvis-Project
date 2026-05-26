import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { JARVIS_COLORS, ANIMATION } from '../utils/constants'
import { useStore } from '../hooks/useStore'

function Orb({ angle, radius }: { angle: number; radius: number }) {
  const mesh = useRef<THREE.Mesh>(null!)

  useFrame((state) => {
    const t = state.clock.elapsedTime
    const a = angle + t * 0.3
    mesh.current.position.x = Math.cos(a) * radius
    mesh.current.position.z = Math.sin(a) * radius
    mesh.current.scale.setScalar(0.5 + Math.sin(t * 2 + angle) * 0.3)
  })

  return (
    <mesh ref={mesh}>
      <sphereGeometry args={[0.08, 8, 8]} />
      <meshBasicMaterial
        color={JARVIS_COLORS.accent}
        transparent
        opacity={0.8}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  )
}

export default function HolographicDisplay() {
  const group = useRef<THREE.Group>(null!)
  const innerRef = useRef<THREE.Mesh>(null!)
  const outerRef = useRef<THREE.Mesh>(null!)
  const glowRef = useRef<THREE.Mesh>(null!)
  const status = useStore((s) => s.status)

  const orbs = useMemo(() =>
    Array.from({ length: 12 }, (_, i) => ({
      angle: (i / 12) * Math.PI * 2,
      radius: 2.2,
    })), [])

  useFrame((state) => {
    const t = state.clock.elapsedTime
    const pulse = Math.sin(t * ANIMATION.pulseDuration) * 0.15 + 0.85

    group.current.rotation.x = Math.sin(t * 0.1) * 0.1
    group.current.rotation.z = Math.sin(t * 0.15) * 0.05
    group.current.rotation.y = t * 0.15

    if (innerRef.current) {
      innerRef.current.rotation.x = Math.PI / 3
      innerRef.current.scale.setScalar(pulse)
    }
    if (outerRef.current) {
      outerRef.current.rotation.x = -Math.PI / 4
      outerRef.current.scale.setScalar(1 + Math.sin(t * 1.5) * 0.05)
    }
    if (glowRef.current) {
      glowRef.current.rotation.x = -Math.PI / 6
    }
  })

  return (
    <group ref={group}>
      <mesh ref={outerRef}>
        <ringGeometry args={[1.8, 2, 64]} />
        <meshBasicMaterial
          color={JARVIS_COLORS.primary}
          transparent
          opacity={0.3}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      <mesh ref={innerRef}>
        <ringGeometry args={[0, 0.02, 32]} />
        <meshBasicMaterial
          color={JARVIS_COLORS.accent}
          transparent
          opacity={0.6}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      <mesh ref={glowRef}>
        <ringGeometry args={[2.5, 3.5, 64]} />
        <meshBasicMaterial
          color={JARVIS_COLORS.primary}
          transparent
          opacity={0.08}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {orbs.map((orb, i) => (
        <Orb key={i} angle={orb.angle} radius={orb.radius} />
      ))}
    </group>
  )
}
