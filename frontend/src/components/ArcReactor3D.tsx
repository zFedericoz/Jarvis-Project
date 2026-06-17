import { useState, useEffect, useRef, memo } from "react";
import { Canvas, useFrame, type GroupProps } from "@react-three/fiber";
import * as THREE from "three";
import type { Group, Mesh } from "three";
import { C } from "../utils/theme";

function ReactorGeometry({ isResponding }: { isResponding: boolean }) {
  const groupRef = useRef<Group>(null!);
  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (groupRef.current) {
      groupRef.current.rotation.y = t * 0.5;
      groupRef.current.rotation.x = 0.5 + Math.sin(t * 0.3) * 0.08;
    }
  });
  return (
    <group ref={groupRef}>
      <mesh><torusGeometry args={[1.4, 0.05, 16, 100]} /><meshBasicMaterial color={isResponding ? C.green : C.cyan} wireframe /></mesh>
      <mesh><torusGeometry args={[1.0, 0.02, 12, 64]} /><meshBasicMaterial color={C.cyanDim} wireframe /></mesh>
      {Array.from({length:10}).map((_,i) => {
        const a = (i/10)*Math.PI*2;
        return (
          <group key={i} rotation={[0,0,a] as unknown as GroupProps['rotation']}>
            <mesh position={[1.2,0,0]}><boxGeometry args={[0.22,0.1,0.15]} /><meshBasicMaterial color={isResponding ? C.green : C.cyan} wireframe /></mesh>
          </group>
        );
      })}
      <mesh><sphereGeometry args={[0.35,32,32]} /><meshBasicMaterial color={isResponding ? "#ffffff" : C.cyan} /></mesh>
    </group>
  );
}

function HolographicWave3D({ id, onRemove }: { id: number; onRemove: (id: number) => void }) {
  const meshRef = useRef<Mesh>(null!);
  useFrame((_s, delta) => {
    if (meshRef.current) {
      meshRef.current.scale.x += delta * 2.8;
      meshRef.current.scale.y += delta * 2.8;
      meshRef.current.scale.z += delta * 2.8;
      (meshRef.current.material as THREE.Material & {opacity:number}).opacity -= delta * 0.75;
      if ((meshRef.current.material as THREE.Material & {opacity:number}).opacity <= 0) onRemove(id);
    }
  });
  return (
    <mesh ref={meshRef} rotation={[0.5,0,0]}>
      <torusGeometry args={[1.4,0.02,8,64]} />
      <meshBasicMaterial color={C.green} transparent opacity={1} wireframe />
    </mesh>
  );
}

export const ArcReactor3D = memo(function ArcReactor3D({ isResponding }: { isResponding: boolean }) {
  const [waves, setWaves] = useState<{id:number}[]>([]);
  useEffect(() => {
    if (!isResponding) return;
    const interval = setInterval(() => setWaves(p => [...p, {id: Date.now()+Math.random()}]), 450);
    return () => clearInterval(interval);
  }, [isResponding]);
  const removeWave = (id:number) => setWaves(p => p.filter(w => w.id !== id));
  return (
    <div style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",height:"100%",width:"100%",position:"relative"}}>
      <div style={{width:"100%",height:"100%"}}>
        <Canvas camera={{position:[0,0,3.8],fov:55}}>
          <ambientLight intensity={0.8} />
          <pointLight position={[5,5,5]} intensity={1.5} />
          <ReactorGeometry isResponding={isResponding} />
          {waves.map(w => <HolographicWave3D key={w.id} id={w.id} onRemove={removeWave} />)}
        </Canvas>
      </div>
    </div>
  );
});
