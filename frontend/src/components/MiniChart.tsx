import { useEffect, useRef } from "react";

export function MiniChart({ data, color, max = 100 }: { data: number[]; color: string; max?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null!);
  useEffect(() => {
    const c = canvasRef.current; if (!c) return;
    const ctx = c.getContext("2d"); if (!ctx) return;
    const W = c.width, H = c.height;
    ctx.clearRect(0,0,W,H);
    ctx.strokeStyle = color; ctx.lineWidth = 1.2; ctx.beginPath();
    const draw = data.length < 2 ? [0,0] : data.slice(-30);
    for (let i = 0; i < draw.length; i++) {
      const x = (i / Math.max(draw.length-1,1)) * W;
      const y = H - (draw[i]/max) * H;
      i === 0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    }
    ctx.stroke();
  });
  return <canvas ref={canvasRef} width={80} height={20} style={{display:"block",width:80,height:20,flexShrink:0}} />;
}
