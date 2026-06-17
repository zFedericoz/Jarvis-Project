import { useRef } from "react";
import { C } from "../utils/theme";
import { useAnimFrame } from "../hooks/useAnimFrame";

export function Waveform({ active, color = C.cyan }: { active: boolean; color?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null!);
  const phase = useRef(0);
  useAnimFrame(() => {
    const c = canvasRef.current; if (!c) return;
    const ctx = c.getContext("2d"); if (!ctx) return;
    const W = c.width, H = c.height;
    ctx.clearRect(0,0,W,H);
    if (!active) { ctx.strokeStyle = `${color}33`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(0,H/2); ctx.lineTo(W,H/2); ctx.stroke(); return; }
    phase.current += 0.15;
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath();
    for (let x = 0; x < W; x++) {
      const t = (x/W)*Math.PI*4;
      const y = H/2 + Math.sin(t+phase.current)*(H*0.35);
      x===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    }
    ctx.stroke();
  });
  return <canvas ref={canvasRef} width={250} height={24} style={{display:"block",width:"100%"}} />;
}
