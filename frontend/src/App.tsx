import { useState, useEffect, useRef, useCallback, type ReactNode, type FormEvent } from "react";
import { Canvas, useFrame, type GroupProps } from "@react-three/fiber";
import * as THREE from "three";
import type { Group, Mesh } from "three";
import Sidebar from "./components/Sidebar";
import { useStore } from "./hooks/useStore";
import { API_URL } from "./utils/constants";

function _md(s:string){return s.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\*(.+?)\*/g,'<i>$1</i>').replace(/`(.+?)`/g,'<code style=\"background:rgba(0,0,0,0.3);border-radius:2px;padding:0 3px;font-size:0.9em\">$1</code>').replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href=\"$2\" style=\"color:#00e5ff;text-decoration:underline\">$1</a>');}

function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: ReactNode[] = [];
  let inCode = false, codeLang = "", codeLines: string[] = [], codeIdx = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("```")) {
      if (inCode) {
        elements.push(<pre key={`c${codeIdx}`} style={{background:"rgba(0,0,0,0.4)",borderRadius:4,padding:"6px 8px",margin:"4px 0",overflow:"auto",fontSize:11,fontFamily:"'JetBrains Mono','Consolas',monospace",lineHeight:1.5}}><code>{codeLines.join("\n")}</code></pre>);
        codeIdx++; codeLines=[]; codeLang=""; inCode=false;
      } else { inCode=true; codeLang=line.slice(3).trim(); }
      continue;
    }
    if (inCode) { codeLines.push(line); continue; }
    if (!line.trim()) { elements.push(<div key={`b${i}`} style={{height:4}} />); continue; }
    const isLi = /^[-*]\s/.test(line) || /^\d+\.\s/.test(line);
    if (isLi) { elements.push(<div key={`l${i}`} style={{display:"flex",gap:6,paddingLeft:8}}><span style={{color:"#00e5ff"}}>•</span><span dangerouslySetInnerHTML={{__html:_md(line.replace(/^[-*\d]+\.\s+/,""))}} /></div>); }
    else { elements.push(<div key={`p${i}`} dangerouslySetInnerHTML={{__html:_md(line)}} />); }
  }
  if (inCode && codeLines.length>0) elements.push(<pre key={`c${codeIdx}`} style={{background:"rgba(0,0,0,0.4)",borderRadius:4,padding:"6px 8px",margin:"4px 0",overflow:"auto",fontSize:11,fontFamily:"'JetBrains Mono','Consolas',monospace",lineHeight:1.5}}><code>{codeLines.join("\n")}</code></pre>);
  return <>{elements}</>;
}

const HOST_METRICS_URL = "http://localhost:18765";
const DOCKER_API = "";

async function fetchFromBest(urls: string[]): Promise<any> {
  for (const url of urls) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(2000) });
      if (r.ok) return r.json();
    } catch {}
  }
  return null;
}

const THEMES = {
  dark: {
    bg: "#050e14", bgPanel: "#071520", bgPanelHover: "#0a1e2e",
    cyan: "#00e5ff", cyanDim: "#00b8cc", cyanFaint: "rgba(0,229,255,0.08)",
    green: "#00ff88", greenDim: "#00cc6a", amber: "#ffaa00",
    red: "#ff4455", purple: "#a855f7",
    border: "rgba(0,229,255,0.18)", borderStrong: "rgba(0,229,255,0.45)",
    text: "#c8eef8", textDim: "rgba(200,238,248,0.6)", textFaint: "rgba(200,238,248,0.3)",
  },
  light: {
    bg: "#f0f4f8", bgPanel: "#e2e8f0", bgPanelHover: "#cbd5e1",
    cyan: "#0284c7", cyanDim: "#0369a1", cyanFaint: "rgba(2,132,199,0.08)",
    green: "#059669", greenDim: "#047857", amber: "#d97706",
    red: "#dc2626", purple: "#7c3aed",
    border: "rgba(2,132,199,0.18)", borderStrong: "rgba(2,132,199,0.45)",
    text: "#0f172a", textDim: "rgba(15,23,42,0.6)", textFaint: "rgba(15,23,42,0.3)",
  },
};

let C = THEMES.dark;
const font = "'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif";
const mono = "'JetBrains Mono', 'Consolas', 'Courier New', monospace";

function useInterval(cb: () => void, ms: number) {
  const ref = useRef(cb);
  useEffect(() => { ref.current = cb; }, [cb]);
  useEffect(() => {
    const id = setInterval(() => ref.current(), ms);
    return () => clearInterval(id);
  }, [ms]);
}

function useAnimFrame(cb: () => void) {
  const ref = useRef(cb);
  useEffect(() => { ref.current = cb; }, [cb]);
  useEffect(() => {
    let id: number;
    const loop = () => { ref.current(); id = requestAnimationFrame(loop); };
    id = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(id);
  }, []);
}

function Scanlines() {
  return (
    <div style={{
      pointerEvents: "none", position: "absolute", inset: 0, zIndex: 9999,
      background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.07) 2px, rgba(0,0,0,0.07) 4px)",
    }} />
  );
}

function Panel({ children, style, title, accent = C.cyan }: {
  children: ReactNode; style?: React.CSSProperties; title?: string; accent?: string;
}) {
  return (
    <div style={{
      background: C.bgPanel, border: `1px solid ${C.border}`,
      borderTop: `1px solid ${accent}55`, borderRadius: 4,
      padding: title ? "8px 10px" : "6px 10px", position: "relative",
      display: "flex", flexDirection: "column", overflow: "hidden", ...style,
    }}>
      {[["0%","0%","top","left"],["100%","0%","top","right"],["0%","100%","bottom","left"],["100%","100%","bottom","right"]].map(([l,t,v,h],i) => (
        <div key={i} style={{
          position:"absolute", [v]: -1, [h]: -1, width: 8, height: 8,
          borderTop: v==="top" ? `1px solid ${accent}` : "none",
          borderBottom: v==="bottom" ? `1px solid ${accent}` : "none",
          borderLeft: h==="left" ? `1px solid ${accent}` : "none",
          borderRight: h==="right" ? `1px solid ${accent}` : "none",
        }}/>
      ))}
      {title && (
        <div style={{ fontFamily: mono, fontSize: 10, letterSpacing: "0.2em", color: C.textDim, marginBottom: 6, textTransform: "uppercase", flexShrink: 0 }}>
          ▸ {title}
        </div>
      )}
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {children}
      </div>
    </div>
  );
}

// ── 3D Reactor ────────────────────────────────────────────────────────────────
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

function ArcReactor3D({ isResponding }: { isResponding: boolean }) {
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
}

// ── Mini Sparkline ─────────────────────────────────────────────────────────────
function MiniChart({ data, color, max = 100 }: { data: number[]; color: string; max?: number }) {
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

// ── Real System Log ───────────────────────────────────────────────────────────
function SystemLog({ compact }: { compact?: boolean }) {
  const [logs, setLogs] = useState<{timestamp:string;level:string;message:string}[]>([]);
  const endRef = useRef<HTMLDivElement>(null!);
  useEffect(() => {
    const fetchLogs = async () => {
      const d = await fetchFromBest([`${HOST_METRICS_URL}/api/system/logs`, `${DOCKER_API}/api/system/logs`]);
      if (d?.logs) setLogs(d.logs.slice(-20));
    };
    fetchLogs(); const id = setInterval(fetchLogs, 3000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => { endRef.current?.scrollIntoView({behavior:"smooth"}); }, [logs]);
  const colorMap: Record<string,string> = {warning:C.amber,error:C.red,info:C.cyan};
  if (compact) {
    const last = logs[logs.length - 1];
    return (
      <span style={{fontFamily:mono,fontSize:11,color: last ? colorMap[last.level] || C.textDim : C.textFaint, whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>
        {last ? last.message : "In attesa di log..."}
      </span>
    );
  }
  return (
    <div style={{fontFamily:mono,fontSize:11,lineHeight:1.6,overflow:"auto",height:"100%",paddingRight:4}}>
      {logs.length === 0 && <div style={{color:C.textFaint}}>In attesa di log di sistema...</div>}
      {logs.map((l,i) => (
        <div key={i} style={{color:colorMap[l.level]||C.textDim,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>
          {l.message}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

// ── Globe (animated WebP) ─────────────────────────────────────────────────────
function GlobeImage() {
  return (
    <div style={{ position:"relative", display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div style={{
        position:"absolute", inset:"10%", borderRadius:"50%",
        boxShadow: `0 0 30px 10px ${C.cyanFaint}, inset 0 0 30px 10px rgba(0,0,0,0.3)`,
        pointerEvents:"none",
      }} />
      <img src="/globe-40.gif.webp" alt="Globe"
        style={{ width:"100%", maxWidth:120, display:"block", borderRadius:"50%" }}
      />
    </div>
  );
}

// ── Waveform ──────────────────────────────────────────────────────────────────
function Waveform({ active, color = C.cyan }: { active: boolean; color?: string }) {
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

// ── Metric bar item ──────────────────────────────────────────────────────────
function MetricBadge({ label, value, unit, color, history }: { label: string; value: string | number; unit: string; color: string; history?: number[] }) {
  return (
    <div style={{display:"flex",alignItems:"center",gap:6,fontFamily:mono,fontSize:12,color:C.text,borderRight:`1px solid ${C.border}`,paddingRight:10}}>
      <span style={{color:C.textFaint,fontSize:10,letterSpacing:"0.05em"}}>{label}</span>
      <span style={{color,fontWeight:"bold",fontSize:14}}>{value}<span style={{fontSize:10,color:C.textDim,marginLeft:1}}>{unit}</span></span>
      {history && <MiniChart data={history} color={color} />}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
interface MetricSnapshot { cpu: number; ram: number; temp: number|null; disk: number; history: { cpu: number[]; ram: number[]; temp: number[]; disk: number[] }; processes: {pid:number;name:string;cpu:number;mem:number}[]; uptime: number; ram_gb: number; ram_total_gb: number; net_sent: number; net_recv: number }

export default function JarvisDashboard() {
  const [metrics, setMetrics] = useState<MetricSnapshot | null>(null);
  const [listening, setListening] = useState(false);
  const [isResponding, setIsResponding] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<{id:number;role:string;text:string;sources?:any[];commands?:string[]}[]>([
    {id:0,role:"system",text:"Sistemi ausiliari inizializzati. Reattore ARC stabile. In attesa di comandi, Signore."}
  ]);
  const [feedbackSent, setFeedbackSent] = useState<Record<number,number>>({});
  const [attachedFiles, setAttachedFiles] = useState<{name:string;content:string}[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [theme, setTheme] = useState<"dark"|"light">("dark");
  const [speedDialOpen, setSpeedDialOpen] = useState(false);
  C = THEMES[theme];
  const msgIdRef = useRef(1);
  const chatEndRef = useRef<HTMLDivElement>(null!);
  const chatContainerRef = useRef<HTMLDivElement>(null!);
  const fileInputRef = useRef<HTMLInputElement>(null!);
  const abortRef = useRef<AbortController | null>(null);

  const { activeSessionId, chatHistory, setChatHistory, addChatHistory } = useStore();

  const sendFeedback = async (msgId:number, rating:number, userMsg:string, assistantMsg:string) => {
    if (feedbackSent[msgId]) return;
    try {
      await fetch(`${DOCKER_API}/api/feedback`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({message_id:String(msgId),user_message:userMsg,assistant_response:assistantMsg,rating,language:"it",intent:"chat"}),
      });
      setFeedbackSent(p => ({...p, [msgId]:rating}));
    } catch {}
  };

  const exportChat = () => {
    const txt = displayMessages.map(m => `${m.role === "user" ? "TU" : "J.A.R.V.I.S."}: ${m.text}`).join("\n\n---\n\n");
    const blob = new Blob([txt], {type:"text/plain;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `jarvis-${new Date().toISOString().slice(0,10)}.txt`; a.click();
    URL.revokeObjectURL(url);
  };

  const fetchMetrics = useCallback(async () => {
    const d = await fetchFromBest([`${HOST_METRICS_URL}/api/system/metrics`, `${DOCKER_API}/api/system/metrics`]);
    if (d) setMetrics(d as MetricSnapshot);
  }, []);

  useEffect(() => { fetchMetrics(); const id = setInterval(fetchMetrics, 2000); return () => clearInterval(id); }, [fetchMetrics]);

  const uploadFile = async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await fetch(`${DOCKER_API}/api/upload`, {method:"POST", body:fd});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setAttachedFiles(p => [...p, {name:d.filename, content:d.content}]);
    } catch (err) {
      console.error("Upload fallito:", err);
    }
  };

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    for (const f of e.target.files || []) uploadFile(f);
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    for (const f of e.dataTransfer.files) uploadFile(f);
  };

  const removeFile = (idx: number) => setAttachedFiles(p => p.filter((_,i) => i !== idx));

  const cpu = metrics?.cpu ?? 0;
  const ram = metrics?.ram ?? 0;
  const temp = metrics?.temp ?? 0;
  const disk = metrics?.disk ?? 0;
  const cpuHist = metrics?.history?.cpu ?? [];
  const ramHist = metrics?.history?.ram ?? [];
  const tempHist = metrics?.history?.temp ?? [];

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsResponding(false);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const hasContent = chatInput.trim() || attachedFiles.length > 0;
    if (!hasContent || isResponding) return;
    const userMsg = chatInput.trim() + (attachedFiles.length > 0 ? `\n\n[File allegati: ${attachedFiles.map(f=>f.name).join(", ")}]` : "");
    const fileContent = attachedFiles.length > 0 ? attachedFiles.map(f => `=== ${f.name} ===\n${f.content}`).join("\n\n") : "";
    const uid = msgIdRef.current++;
    setMessages(p => [...p, {id:uid,role:"user",text:userMsg}]);
    setChatInput("");
    setAttachedFiles([]);
    setIsResponding(true);

    let sid = 0;
    let sessionIdReturned: number | null = null;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    abortRef.current = controller;
    try {
      const r = await fetch(`${DOCKER_API}/api/chat`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({text:userMsg, file_content: fileContent, session_id: activeSessionId ?? undefined, stream: true}),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      abortRef.current = null;
      if (!r.ok) throw new Error(`HTTP ${r.status}`);

      const reader = r.body?.getReader();
      if (!reader) { setIsResponding(false); return; }
      const decoder = new TextDecoder();
      let buffer = "";
      let responseText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);
          try {
            const ev = JSON.parse(data);
            if (ev.type === "token") {
              responseText += ev.text;
              if (sid === 0) { sid = msgIdRef.current++; setMessages(p => [...p, {id:sid,role:"system",text:""}]); }
              setMessages(p => p.map(m => m.id === sid ? {...m, text: responseText} : m));
            } else if (ev.type === "done") {
              responseText = ev.response;
              if (sid === 0) { sid = msgIdRef.current++; }
              setMessages(p => p.map(m => m.id === sid ? {...m, text: responseText, sources: ev.sources || []} : m));
              sessionIdReturned = ev.session_id;
            }
          } catch {}
        }
      }

      if (sessionIdReturned && !activeSessionId) {
        useStore.getState().setActiveSessionId(sessionIdReturned);
        const sr = await fetch(`${API_URL}/chats`);
        const sj = await sr.json();
        if (sj.sessions) { useStore.getState().setSessions(sj.sessions); }
      }
    } catch (err) {
      const aborted = (err as Error)?.name === "AbortError";
      clearTimeout(timeout);
      abortRef.current = null;
      const eid = msgIdRef.current++;
      if (aborted) {
        setMessages(p => [...p, {id:eid,role:"system",text:"Richiesta interrotta."}]);
      } else {
        setMessages(p => [...p, {id:eid,role:"system",text:"Errore di connessione al server. Verifica che il backend sia in esecuzione."}]);
      }
    }
    setIsResponding(false);
  };

  useEffect(() => { chatEndRef.current?.scrollIntoView({behavior:"smooth"}); }, [messages]);

  const displayMessages = activeSessionId && chatHistory.length > 0
    ? [{id:0,role:"system",text:"Sistemi ausiliari inizializzati."}, ...chatHistory.map((m,i) => ({id:i+1,role:m.role,text:m.content}))]
    : messages;

  return (
    <div style={{background:C.bg,height:"100vh",width:"100vw",overflow:"hidden",fontFamily:font,color:C.text,position:"relative",display:"flex",flexDirection:"column",boxSizing:"border-box"}}>
      <Scanlines />

      {/* ── TOP METRICS BAR ── */}
      <div style={{flexShrink:0,display:"flex",alignItems:"center",gap:10,padding:"6px 14px",borderBottom:`1px solid ${C.border}`,background:C.bgPanel}}>
        <div style={{flexShrink:0,marginRight:4}}>
          <span style={{fontSize:14,letterSpacing:"0.3em",color:C.cyan,fontWeight:"bold",fontFamily:mono}}>J.A.R.V.I.S</span>
        </div>
        <MetricBadge label="CPU" value={Math.round(cpu)} unit="%" color={C.cyan} history={cpuHist} />
        <MetricBadge label="RAM" value={Math.round(ram)} unit="%" color={C.green} history={ramHist} />
        <MetricBadge label="TEMP" value={temp ? Math.round(temp) : "—"} unit="°C" color={C.amber} history={tempHist} />
        <MetricBadge label="DISK" value={Math.round(disk)} unit="%" color={C.text} />
        <div style={{flex:1,minWidth:0,display:"flex",alignItems:"center",paddingLeft:8}}>
          <SystemLog compact />
        </div>
        <div style={{fontFamily:mono,fontSize:12,color:C.textFaint,flexShrink:0,display:"flex",alignItems:"center",gap:8}}>
          <span onClick={()=>setTheme(t=>t==="dark"?"light":"dark")}
            style={{cursor:"pointer",fontSize:14,color:C.amber,transition:"transform 0.2s"}}
            title="Cambia tema">{theme==="dark"?"☀️":"🌙"}</span>
          <span onClick={exportChat}
            style={{cursor:"pointer",fontSize:12,color:C.textDim}}
            title="Esporta conversazione">📥</span>
          {new Date().toLocaleTimeString('it-IT')}
        </div>
      </div>

      {/* ── MAIN LAYOUT ── */}
      <div style={{flex:1,display:"grid",gridTemplateColumns:"240px 1fr",gap:0,minHeight:0}}>

        {/* SIDEBAR */}
        <div style={{overflow:"hidden",borderRight:`1px solid ${C.border}`}}>
          <Sidebar />
        </div>

        {/* CENTER: Reactor + Chat */}
        <div style={{display:"flex",flexDirection:"column",minHeight:0,padding:"8px 10px",gap:8}}>

          {/* Reactor */}
          <div style={{flex:1,background:"rgba(0,0,0,0.2)",borderRadius:4,border:`1px solid ${C.cyanFaint}`,overflow:"hidden",position:"relative",minHeight:120}}>
            <ArcReactor3D isResponding={isResponding} />
          </div>

          {/* Quick action buttons */}
          <div style={{flexShrink:0,display:"flex",gap:4,flexWrap:"wrap"}}>
            {[
              {icon:"📸",label:"Screenshot",cmd:"Fai uno screenshot"},
              {icon:"⎇",label:"Terminale",cmd:"apri il terminale"},
              {icon:"🔒",label:"Blocca PC",cmd:"blocca il PC"},
              {icon:"📊",label:"Git status",cmd:"git status"},
            ].map((a,i) => (
              <button key={i} onClick={()=>{setChatInput(a.cmd);setTimeout(()=>document.querySelector<HTMLFormElement>('form')?.requestSubmit(),50)}}
                style={{fontSize:11,fontFamily:"'JetBrains Mono','Consolas',monospace",background:C.cyanFaint,border:`1px solid ${C.border}`,color:C.cyanDim,borderRadius:3,padding:"2px 8px",cursor:"pointer",display:"flex",alignItems:"center",gap:4,transition:"background 0.15s"}}
                onMouseEnter={e=>(e.currentTarget.style.background=C.cyanFaint?.replace("0.08","0.15"))}
                onMouseLeave={e=>(e.currentTarget.style.background=C.cyanFaint)}
                title={a.cmd}>{a.icon} {a.label}</button>
            ))}
          </div>

          {/* Chat messages */}
          {displayMessages.length > 1 && (
            <div ref={chatContainerRef}
              onDragOver={e=>{e.preventDefault();setDragOver(true);}}
              onDragLeave={()=>setDragOver(false)}
              onDrop={handleDrop}
              style={{maxHeight:160,overflowY:"auto",display:"flex",flexDirection:"column",gap:4,padding:"4px 6px",background:dragOver?"rgba(0,229,255,0.08)":"rgba(0,0,0,0.15)",borderRadius:4,border:`1px solid ${dragOver?C.cyan:C.cyanFaint}`,transition:"background 0.15s, border-color 0.15s"}}>
              {displayMessages.slice(1).map((msg,i,arr) => {
                const prevUser = msg.role==="system" ? arr.slice(0,i).reverse().find(m => m.role==="user") : null;
                return (
                <div key={msg.id} style={{
                  alignSelf: msg.role==="user" ? "flex-end" : "flex-start",
                  background: msg.role==="user" ? C.cyanFaint : "rgba(0,255,136,0.05)",
                  borderLeft: msg.role==="system" ? `2px solid ${C.green}` : "none",
                  borderRight: msg.role==="user" ? `2px solid ${C.cyan}` : "none",
                  padding:"4px 8px",borderRadius:4,maxWidth:"85%",fontSize:13,lineHeight:1.4,position:"relative",
                }}>
                  <span style={{fontSize:9,color:msg.role==="user"?C.cyan:C.green,display:"block",marginBottom:1,fontFamily:mono,letterSpacing:"0.05em"}}>
                    {msg.role==="user" ? "TU" : "J.A.R.V.I.S."}
                  </span>
                  {msg.role === "system" ? <MarkdownRenderer content={msg.text} /> : msg.text}
                  {msg.role==="system" && prevUser && (
                    <div style={{display:"flex",gap:4,marginTop:4}}>
                      <span onClick={() => sendFeedback(msg.id,2,prevUser.text,msg.text)}
                        style={{cursor:"pointer",fontSize:13,color:feedbackSent[msg.id]===2?C.green:C.textFaint,opacity:0.6}}>▲</span>
                      <span onClick={() => sendFeedback(msg.id,1,prevUser.text,msg.text)}
                        style={{cursor:"pointer",fontSize:13,color:feedbackSent[msg.id]===1?C.red:C.textFaint,opacity:0.6}}>▼</span>
                    </div>
                  )}
                  {(msg as any).sources?.length > 0 && (
                    <div style={{marginTop:4,display:"flex",gap:6,flexWrap:"wrap"}}>
                      {(msg as any).sources.map((s:any,i:number) => (
                        <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
                          style={{fontSize:10,fontFamily:"'JetBrains Mono','Consolas',monospace",color:"#00e5ff",textDecoration:"none",border:"1px solid rgba(0,229,255,0.25)",borderRadius:3,padding:"1px 6px",opacity:0.7}}
                          title={s.url}>📰 {s.title}</a>
                      ))}
                    </div>
                  )}
                </div>
                );
              })}
              <div ref={chatEndRef} />
            </div>
          )}

          {/* Waveform + Mic */}
          <div style={{flexShrink:0,display:"flex",gap:8,alignItems:"center"}}>
            <button onClick={()=>setListening(!listening)} style={{width:32,height:32,borderRadius:"50%",background:listening?C.cyanFaint:"transparent",border:`1px solid ${listening?C.cyan:C.border}`,color:listening?C.cyan:C.textDim,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,fontSize:12}}>
              {listening ? "●" : "🎤"}
            </button>
            <div style={{flex:1,background:C.bgPanel,border:`1px solid ${C.border}`,borderRadius:16,padding:"0 10px",height:28,display:"flex",alignItems:"center"}}>
              <Waveform active={listening||isResponding} color={isResponding?C.green:C.cyan} />
            </div>
          </div>

          {/* File chips */}
          {attachedFiles.length > 0 && (
            <div style={{flexShrink:0,display:"flex",gap:6,flexWrap:"wrap"}}>
              {attachedFiles.map((f,i) => (
                <span key={i} style={{fontSize:12,fontFamily:mono,background:"rgba(0,229,255,0.12)",border:`1px solid ${C.cyan}`,borderRadius:4,padding:"3px 10px",display:"flex",alignItems:"center",gap:6,color:C.cyan,boxShadow:"0 0 8px rgba(0,229,255,0.12)"}}>
                  <span style={{fontSize:14}}>📎</span> {f.name}
                  <span onClick={()=>removeFile(i)} style={{cursor:"pointer",color:C.red,fontSize:15,lineHeight:"14px",fontWeight:"bold",marginLeft:2,opacity:0.8}} title="Rimuovi">×</span>
                </span>
              ))}
            </div>
          )}

          {/* Speed dial */}
          <div style={{flexShrink:0}}>
            <button onClick={()=>setSpeedDialOpen(!speedDialOpen)}
              style={{fontSize:11,fontFamily:mono,background:"transparent",border:`1px solid ${C.border}`,color:C.textDim,borderRadius:3,padding:"1px 8px",cursor:"pointer",width:"100%"}}>
              {speedDialOpen ? "▼" : "▶"} Comandi rapidi
            </button>
            {speedDialOpen && (
              <div style={{display:"flex",gap:4,flexWrap:"wrap",marginTop:4}}>
                {["Che ore sono?","Raccontami una barzelletta","Fai un briefing","Cerca su web ultime notizie","Apri Visual Studio Code","Scrivi una poesia"].map((cmd,i) => (
                  <button key={i} onClick={()=>{setChatInput(cmd);setTimeout(()=>document.querySelector<HTMLFormElement>('form')?.requestSubmit(),50)}}
                    style={{fontSize:10,fontFamily:mono,background:C.cyanFaint,border:`1px solid ${C.border}`,color:C.cyanDim,borderRadius:3,padding:"1px 6px",cursor:"pointer",whiteSpace:"nowrap"}}>{cmd}</button>
                ))}
              </div>
            )}
          </div>

          {/* Input */}
          <form onSubmit={handleSubmit} style={{flexShrink:0,display:"flex",gap:6,alignItems:"center"}}>
            <input type="file" ref={fileInputRef} onChange={handleFilePick} style={{display:"none"}} multiple />
            <button type="button" onClick={()=>fileInputRef.current?.click()}
              style={{width:36,height:36,flexShrink:0,background:"rgba(0,229,255,0.08)",border:`1px solid ${C.cyan}`,color:C.cyan,cursor:"pointer",borderRadius:4,display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,boxShadow:"0 0 6px rgba(0,229,255,0.15)",transition:"background 0.15s"}}
              title="Allega file (docx, xlsx, pdf, codice...)"
              onMouseEnter={e=>(e.currentTarget.style.background="rgba(0,229,255,0.18)")}
              onMouseLeave={e=>(e.currentTarget.style.background="rgba(0,229,255,0.08)")}
            >📎</button>
            <input type="text" value={chatInput} onChange={e=>setChatInput(e.target.value)}
              placeholder="Invia una direttiva testuale a J.A.R.V.I.S..."
              disabled={isResponding}
              style={{flex:1,background:"rgba(0,0,0,0.25)",border:`1px solid ${C.border}`,color:C.text,fontFamily:font,fontSize:14,padding:"8px 12px",outline:"none",borderRadius:4}}
            />
            {isResponding ? (
              <button type="button" onClick={handleStop}
                style={{background:"rgba(255,68,85,0.15)",border:`1px solid ${C.red}`,color:C.red,fontFamily:mono,fontSize:12,padding:"0 14px",cursor:"pointer",borderRadius:4}}
              >
                ⏹ STOP
              </button>
            ) : (
              <button type="submit" disabled={!chatInput.trim() && attachedFiles.length === 0}
                style={{background:"rgba(0,229,255,0.1)",border:`1px solid ${C.cyan}`,color:C.cyan,fontFamily:mono,fontSize:12,padding:"0 14px",cursor:"pointer",borderRadius:4}}
              >
                EXEC
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
