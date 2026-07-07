import { useEffect, useRef } from "react";
import * as THREE from "three";
import { C } from "../../utils/theme";

interface HUDProps {
  isResponding: boolean;
  isListening: boolean;
  volume: number;
}

export default function HolographicHUD({ isResponding, isListening, volume }: HUDProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const scanLineRef = useRef<number>(0);
  const particlesRef = useRef<THREE.Points | null>(null);
  const ringRef = useRef<THREE.Mesh | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, mount.clientWidth / mount.clientHeight, 0.1, 100);
    camera.position.z = 5;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    // ── Anelli olografici concentrici ──
    const ringGeo = new THREE.TorusGeometry(1.6, 0.02, 16, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: C.cyan, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = Math.PI / 3;
    scene.add(ring);

    const ring2Geo = new THREE.TorusGeometry(2.0, 0.015, 16, 64);
    const ring2Mat = new THREE.MeshBasicMaterial({
      color: C.green, transparent: true, opacity: 0.25, blending: THREE.AdditiveBlending,
    });
    const ring2 = new THREE.Mesh(ring2Geo, ring2Mat);
    ring2.rotation.x = -Math.PI / 4;
    scene.add(ring2);

    // ── Particelle fluttuanti ──
    const particleCount = 200;
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 6;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 6;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 4;
      const c = new THREE.Color(C.cyan).lerp(new THREE.Color(C.green), Math.random());
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    }
    const particleGeo = new THREE.BufferGeometry();
    particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    particleGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const particleMat = new THREE.PointsMaterial({
      size: 0.04, vertexColors: true, transparent: true, opacity: 0.6,
      blending: THREE.AdditiveBlending, sizeAttenuation: true,
    });
    const particles = new THREE.Points(particleGeo, particleMat);
    scene.add(particles);

    // ── Linee digitali (griglia olografica) ──
    const gridHelper = new THREE.GridHelper(5, 12, C.cyan, `${C.cyan}44`);
    gridHelper.position.y = -1.8;
    scene.add(gridHelper);

    sceneRef.current = scene;
    cameraRef.current = camera;
    rendererRef.current = renderer;
    particlesRef.current = particles;
    ringRef.current = ring;

    const animate = () => {
      if (!scene || !camera || !renderer) return;

      const t = Date.now() * 0.001;
      ring.rotation.z += 0.005;
      ring2.rotation.z -= 0.003;
      particles.rotation.y += 0.001;

      // Pulse da volume
      const pulse = 1 + volume * 0.5;
      ring.scale.set(pulse, pulse, pulse);

      // Glow da risposta
      const glow = isResponding ? 1 : 0.3;
      ringMat.opacity = 0.2 + glow * 0.3;

      // Linea di scansione
      scanLineRef.current = (scanLineRef.current + 0.02) % 2;
      gridHelper.position.y = -1.8 + (scanLineRef.current - 1) * 0.1;

      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    };
    animate();

    const handleResize = () => {
      if (!mount || !camera || !renderer) return;
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      if (mount && renderer.domElement) mount.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, []);

  return (
    <div ref={mountRef} style={{
      width: "100%", height: "100%", position: "relative", overflow: "hidden",
      background: "radial-gradient(ellipse at center, rgba(0,20,30,0.4) 0%, transparent 70%)",
    }}>
      <div style={{
        position: "absolute", bottom: 10, left: "50%", transform: "translateX(-50%)",
        fontSize: 9, fontFamily: "monospace", color: `${C.cyan}88`, letterSpacing: "0.2em",
      }}>
        {isResponding ? "◇ ELABORAZIONE IN CORSO ◇" : isListening ? "■ ASCOLTO ATTIVO ■" : "● SISTEMI PRONTI ●"}
      </div>
    </div>
  );
}
