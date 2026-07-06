import { useEffect, useRef, useState } from "react";
import { C, mono } from "../utils/theme";
import { fetchWithAuth } from "../utils/fetch";

interface VecPoint {
  id: string; text: string; metadata: Record<string,unknown>; embedding: number[]|null;
}

export default function VectorViz({ onClose }: { onClose:()=>void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<Record<string,VecPoint[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [hovered, setHovered] = useState<VecPoint|null>(null);
  const [selectedCol, setSelectedCol] = useState("memories");

  useEffect(() => {
    fetchWithAuth("/api/vectors").then(r=>r.json()).then(d=>{
      if (d.collections) setData(d.collections);
      else setError(d.detail || "Errore caricamento");
    }).catch(e=>setError(String(e))).finally(()=>setLoading(false));
  }, []);

  const points = data[selectedCol] || [];
  const hasEmbeddings = points.some(p => p.embedding && p.embedding.length >= 2);

  useEffect(() => {
    const cvs = canvasRef.current;
    if (!cvs || points.length === 0 || !hasEmbeddings) return;
    const ctx = cvs.getContext("2d");
    if (!ctx) return;

    const W = cvs.width = cvs.clientWidth * devicePixelRatio;
    const H = cvs.height = cvs.clientHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const w = cvs.clientWidth, h = cvs.clientHeight;

    ctx.fillStyle = "rgba(0,0,0,0.85)";
    ctx.fillRect(0, 0, w, h);

    const valid = points.filter(p => p.embedding && p.embedding.length >= 2) as (VecPoint & {embedding:number[]})[];
    if (valid.length === 0) return;

    const xs = valid.map(p => p.embedding[0]);
    const ys = valid.map(p => p.embedding[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const pad = 20;
    const scaleX = (maxX === minX) ? 1 : (w - 2*pad) / (maxX - minX);
    const scaleY = (maxY === minY) ? 1 : (h - 2*pad) / (maxY - minY);

    const colors = [C.cyan, C.green, C.amber, C.cyan, C.green];

    valid.forEach((p, i) => {
      const x = pad + (p.embedding[0] - minX) * scaleX;
      const y = pad + (p.embedding[1] - minY) * scaleY;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, 2*Math.PI);
      ctx.fillStyle = colors[i % colors.length];
      ctx.fill();
    });
  }, [points, hasEmbeddings]);

  const handleMouse = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const rect = cvs.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const valid = points.filter(p => p.embedding && p.embedding.length >= 2) as (VecPoint & {embedding:number[]})[];
    const pad = 20;
    const w = cvs.clientWidth, h = cvs.clientHeight;
    const xs = valid.map(p => p.embedding[0]);
    const ys = valid.map(p => p.embedding[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const scaleX = (maxX === minX) ? 1 : (w - 2*pad) / (maxX - minX);
    const scaleY = (maxY === minY) ? 1 : (h - 2*pad) / (maxY - minY);

    for (const p of valid) {
      const x = pad + (p.embedding[0] - minX) * scaleX;
      const y = pad + (p.embedding[1] - minY) * scaleY;
      if (Math.abs(mx - x) < 6 && Math.abs(my - y) < 6) {
        setHovered(p);
        return;
      }
    }
    setHovered(null);
  };

  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.7)",display:"flex",justifyContent:"center",alignItems:"center",zIndex:1000}} onClick={onClose}>
      <div style={{background:"#111",border:`1px solid ${C.border}`,borderRadius:8,padding:16,maxWidth:"90vw",maxHeight:"90vh",width:800,height:600}} onClick={e=>e.stopPropagation()}>
        <div style={{display:"flex",justifyContent:"space-between",marginBottom:8}}>
          <div style={{display:"flex",gap:8}}>
            {["memories","knowledge","preferences"].map(k => (
              <button key={k} onClick={()=>setSelectedCol(k)}
                style={{background:selectedCol===k?C.cyanFaint:"transparent",border:`1px solid ${C.border}`,borderRadius:3,color:C.text,fontSize:11,cursor:"pointer",padding:"2px 8px",fontFamily:mono}}>
                {k}
              </button>
            ))}
          </div>
          <span onClick={onClose} style={{cursor:"pointer",color:C.textFaint,fontSize:16}}>✕</span>
        </div>
        {loading && <div style={{color:C.textDim,fontFamily:mono,fontSize:12}}>Caricamento vettori...</div>}
        {error && <div style={{color:C.red,fontFamily:mono,fontSize:12}}>{error}</div>}
        {!loading && !error && !hasEmbeddings && (
          <div style={{color:C.textDim,fontFamily:mono,fontSize:12}}>Nessun embedding disponibile (usa ChromaDB con `all-MiniLM-L6-v2`)</div>
        )}
        <canvas ref={canvasRef} onMouseMove={handleMouse}
          style={{width:"100%",height:"calc(100% - 60px)",borderRadius:4,display:hasEmbeddings?"block":"none"}} />
        {hovered && (
          <div style={{fontSize:11,color:C.text,fontFamily:mono,marginTop:4,background:"rgba(0,0,0,0.7)",padding:"4px 8px",borderRadius:3}}>
            <strong>{hovered.id.slice(0,20)}</strong>: {hovered.text.slice(0,120)}
          </div>
        )}
        <div style={{fontSize:10,color:C.textFaint,fontFamily:mono,marginTop:4}}>
          {points.length} punti · prime 2 dimensioni dell'embedding
        </div>
      </div>
    </div>
  );
}
