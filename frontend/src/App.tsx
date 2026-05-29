import { useState, useEffect, useRef, useCallback, type ReactNode, type FormEvent } from "react";
import { Canvas, useFrame, type GroupProps } from "@react-three/fiber";
import * as THREE from "three";
import type { Group, Mesh } from "three";

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

const C = {
  bg: "#050e14", bgPanel: "#071520", bgPanelHover: "#0a1e2e",
  cyan: "#00e5ff", cyanDim: "#00b8cc", cyanFaint: "rgba(0,229,255,0.08)",
  green: "#00ff88", greenDim: "#00cc6a", amber: "#ffaa00",
  red: "#ff4455", purple: "#a855f7",
  border: "rgba(0,229,255,0.18)", borderStrong: "rgba(0,229,255,0.45)",
  text: "#c8eef8", textDim: "rgba(200,238,248,0.6)", textFaint: "rgba(200,238,248,0.3)",
};

const mono = "'Share Tech Mono', 'Courier New', monospace";

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
      padding: "10px 12px", position: "relative",
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
        <div style={{ fontFamily: mono, fontSize: 10, letterSpacing: "0.2em", color: C.textDim, marginBottom: 8, textTransform: "uppercase", flexShrink: 0 }}>
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
      <div style={{width:"100%",height:"85%"}}>
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

// ── Line Chart ────────────────────────────────────────────────────────────────
function LineChart({ data, color, max = 100, label }: { data: number[]; color: string; max?: number; label: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null!);
  useEffect(() => {
    const c = canvasRef.current; if (!c) return;
    const ctx = c.getContext("2d"); if (!ctx) return;
    const W = c.width, H = c.height, pad = 18;
    ctx.clearRect(0,0,W,H);
    const val = data.length > 0 ? data[data.length-1] : 0;
    ctx.fillStyle = C.text; ctx.font = "9px monospace";
    ctx.textAlign = "right"; ctx.fillText(`${Math.round(val)}${label}`, W-2, 10);
    ctx.textAlign = "left"; ctx.fillStyle = C.textFaint; ctx.fillText(label, 2, 10);
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath();
    const draw = data.length < 2 ? [0,0] : data;
    for (let i = 0; i < draw.length; i++) {
      const x = pad + (i / Math.max(draw.length-1,1)) * (W-pad*2);
      const y = H-4 - (draw[i]/max) * (H-14);
      i === 0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    }
    ctx.stroke();
    ctx.fillStyle = color; ctx.globalAlpha = 0.08;
    const last = draw.length-1;
    ctx.lineTo(pad+(last/Math.max(last,1))*(W-pad*2), H-4);
    ctx.lineTo(pad, H-4);
    ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1;
  });
  return <canvas ref={canvasRef} width={280} height={50} style={{display:"block",width:"100%",height:50}} />;
}

// ── Real System Log ───────────────────────────────────────────────────────────
function SystemLog() {
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
  return (
    <div style={{fontFamily:mono,fontSize:10,lineHeight:1.6,overflow:"auto",height:"100%",paddingRight:4}}>
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
        style={{ width:"100%", maxWidth:260, display:"block", borderRadius:"50%" }}
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
  return <canvas ref={canvasRef} width={250} height={28} style={{display:"block",width:"100%"}} />;
}

// ── Main ──────────────────────────────────────────────────────────────────────
interface MetricSnapshot { cpu: number; ram: number; temp: number|null; disk: number; history: { cpu: number[]; ram: number[]; temp: number[]; disk: number[] }; processes: {pid:number;name:string;cpu:number;mem:number}[]; uptime: number; ram_gb: number; ram_total_gb: number; net_sent: number; net_recv: number }

export default function JarvisDashboard() {
  const [metrics, setMetrics] = useState<MetricSnapshot | null>(null);
  const [listening, setListening] = useState(false);
  const [isResponding, setIsResponding] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<{id:number;role:string;text:string}[]>([
    {id:0,role:"system",text:"Sistemi ausiliari inizializzati. Reattore ARC stabile. In attesa di comandi, Signore."}
  ]);
  const [feedbackSent, setFeedbackSent] = useState<Record<number,number>>({});
  const msgIdRef = useRef(1);
  const chatEndRef = useRef<HTMLDivElement>(null!);
  const chatContainerRef = useRef<HTMLDivElement>(null!);
  const abortRef = useRef<AbortController | null>(null);

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

  const fetchMetrics = useCallback(async () => {
    const d = await fetchFromBest([`${HOST_METRICS_URL}/api/system/metrics`, `${DOCKER_API}/api/system/metrics`]);
    if (d) setMetrics(d as MetricSnapshot);
  }, []);

  useEffect(() => { fetchMetrics(); const id = setInterval(fetchMetrics, 2000); return () => clearInterval(id); }, [fetchMetrics]);

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
    if (!chatInput.trim() || isResponding) return;
    const userMsg = chatInput.trim();
    const uid = msgIdRef.current++;
    setMessages(p => [...p, {id:uid,role:"user",text:userMsg}]);
    setChatInput("");
    setIsResponding(true);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    abortRef.current = controller;
    try {
      const r = await fetch(`${DOCKER_API}/api/chat`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({text:userMsg}),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      abortRef.current = null;
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      const sid = msgIdRef.current++;
      setMessages(p => [...p, {id:sid,role:"system",text:d.response || d.detail || "OK"}]);
    } catch (err) {
      const aborted = (err as Error)?.name === "AbortError";
      clearTimeout(timeout);
      abortRef.current = null;
      const eid = msgIdRef.current++;
      if (aborted) {
        setMessages(p => [...p, {id:eid,role:"system",text:"Richiesta interrotta."}]);
      } else {
        setMessages(p => [...p, {id:eid,role:"system",text:`Errore di connessione al server. Verifica che il backend sia in esecuzione.`}]);
      }
    }
    setIsResponding(false);
  };

  useEffect(() => { chatEndRef.current?.scrollIntoView({behavior:"smooth"}); }, [messages]);

  return (
    <div style={{background:C.bg,height:"100vh",width:"100vw",overflow:"hidden",fontFamily:mono,color:C.text,position:"relative",display:"flex",flexDirection:"column",padding:"10px 16px",boxSizing:"border-box"}}>
      <Scanlines />

      {/* HEADER */}
      <div style={{flexShrink:0,display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8,paddingBottom:6,borderBottom:`1px solid ${C.border}`}}>
        <div>
          <div style={{fontSize:16,letterSpacing:"0.3em",color:C.cyan,fontWeight:"bold"}}>J.A.R.V.I.S</div>
          <div style={{fontSize:9,letterSpacing:"0.2em",color:C.textFaint}}>MARK VII INTERFACE INTEGRATION</div>
        </div>
        <div style={{fontSize:13,color:C.cyan,letterSpacing:"0.1em"}}>{new Date().toLocaleTimeString('it-IT')}</div>
      </div>

      {/* MAIN GRID */}
      <div style={{flex:1,display:"grid",gridTemplateColumns:"260px 1fr 240px",gap:12,minHeight:0}}>
        
        {/* LEFT: Charts + Logs */}
        <div style={{display:"flex",flexDirection:"column",gap:10,minHeight:0}}>
          <Panel title="CPU" accent={C.cyan}>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:2}}>
              <div style={{fontSize:22,color:C.cyan,fontWeight:"bold"}}>{Math.round(cpu)}<span style={{fontSize:11,color:C.textDim}}>%</span></div>
              <div style={{flex:1,height:4,background:"rgba(0,229,255,0.1)",borderRadius:2}}>
                <div style={{width:`${Math.min(cpu,100)}%`,height:"100%",background:C.cyan,borderRadius:2}} />
              </div>
            </div>
            <LineChart data={cpuHist} color={C.cyan} max={100} label="%" />
          </Panel>
          <Panel title="RAM" accent={C.green}>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:2}}>
              <div style={{fontSize:22,color:C.green,fontWeight:"bold"}}>{Math.round(ram)}<span style={{fontSize:11,color:C.textDim}}>%</span></div>
              <div style={{flex:1,height:4,background:"rgba(0,255,136,0.1)",borderRadius:2}}>
                <div style={{width:`${Math.min(ram,100)}%`,height:"100%",background:C.green,borderRadius:2}} />
              </div>
              {metrics && <div style={{fontSize:9,color:C.textFaint}}>{metrics.ram_gb}/{metrics.ram_total_gb}GB</div>}
            </div>
            <LineChart data={ramHist} color={C.green} max={100} label="%" />
          </Panel>
          <Panel title="Temperatura" accent={C.amber}>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:2}}>
              <div style={{fontSize:22,color:C.amber,fontWeight:"bold"}}>{temp ? Math.round(temp) : "—"}<span style={{fontSize:11,color:C.textDim}}>°C</span></div>
              <div style={{flex:1,height:4,background:"rgba(255,170,0,0.1)",borderRadius:2}}>
                <div style={{width:`${Math.min(temp?temp/100*100:0,100)}%`,height:"100%",background:C.amber,borderRadius:2}} />
              </div>
            </div>
            <LineChart data={tempHist} color={C.amber} max={100} label="°C" />
          </Panel>
          <div style={{flex:1,minHeight:0}}>
            <Panel title="System Log" style={{height:"100%"}}>
              <SystemLog />
            </Panel>
          </div>
        </div>

        {/* CENTER: Reactor + Chat */}
        <div style={{display:"flex",flexDirection:"column",gap:10,minHeight:0}}>
          <div style={{flex:1,background:"rgba(0,0,0,0.15)",borderRadius:4,border:`1px solid ${C.cyanFaint}`,overflow:"hidden",position:"relative"}}>
            <div style={{position:"absolute",inset:0,display:"flex",flexDirection:"column",zIndex:1}}>
              <div style={{flex:1}} />
              {messages.length > 1 && (
                <div ref={chatContainerRef} style={{maxHeight:"55%",overflowY:"auto",padding:"6px 10px",display:"flex",flexDirection:"column",gap:6}}>
                  {messages.slice(1).map((msg,i,arr) => {
                    const prevUser = msg.role==="system" ? arr.slice(0,i).reverse().find(m => m.role==="user") : null;
                    return (
                    <div key={msg.id} style={{
                      alignSelf: msg.role==="user" ? "flex-end" : "flex-start",
                      background: msg.role==="user" ? C.cyanFaint : "rgba(0,255,136,0.05)",
                      borderLeft: msg.role==="system" ? `2px solid ${C.green}` : "none",
                      borderRight: msg.role==="user" ? `2px solid ${C.cyan}` : "none",
                      padding:"5px 8px",borderRadius:4,maxWidth:"90%",fontSize:10,lineHeight:1.4,position:"relative",
                    }}>
                      <span style={{fontSize:8,color:msg.role==="user"?C.cyan:C.green,display:"block",marginBottom:1}}>
                        {msg.role==="user" ? "TU" : "J.A.R.V.I.S."}
                      </span>
                      {msg.text}
                      {msg.role==="system" && prevUser && (
                        <div style={{display:"flex",gap:4,marginTop:4}}>
                          <span onClick={() => sendFeedback(msg.id,2,prevUser.text,msg.text)}
                            style={{cursor:"pointer",fontSize:11,color:feedbackSent[msg.id]===2?C.green:C.textFaint,opacity:0.6}}>▲</span>
                          <span onClick={() => sendFeedback(msg.id,1,prevUser.text,msg.text)}
                            style={{cursor:"pointer",fontSize:11,color:feedbackSent[msg.id]===1?C.red:C.textFaint,opacity:0.6}}>▼</span>
                        </div>
                      )}
                    </div>
                    );
                  })}
                  <div ref={chatEndRef} />
                </div>
              )}
            </div>
            <ArcReactor3D isResponding={isResponding} />
          </div>

          {/* Controls */}
          <div style={{flexShrink:0,display:"flex",flexDirection:"column",gap:6,padding:"0 8px"}}>
            <div style={{display:"flex",gap:10,alignItems:"center"}}>
              <button onClick={()=>setListening(!listening)} style={{width:36,height:36,borderRadius:"50%",background:listening?C.cyanFaint:"transparent",border:`1px solid ${listening?C.cyan:C.border}`,color:listening?C.cyan:C.textDim,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,fontSize:12}}>
                {listening ? "●" : "🎤"}
              </button>
              <div style={{flex:1,background:C.bgPanel,border:`1px solid ${C.border}`,borderRadius:18,padding:"0 12px",height:36,display:"flex",alignItems:"center"}}>
                <Waveform active={listening||isResponding} color={isResponding?C.green:C.cyan} />
              </div>
            </div>

            <form onSubmit={handleSubmit} style={{display:"flex",justifyContent:"center",padding:"0 10%"}}>
              <div style={{display:"flex",gap:8,width:"100%",maxWidth:500}}>
                <input type="text" value={chatInput} onChange={e=>setChatInput(e.target.value)}
                  placeholder="Invia una direttiva testuale a J.A.R.V.I.S..."
                  disabled={isResponding}
                  style={{flex:1,background:"rgba(0,0,0,0.25)",border:`1px solid ${C.border}`,color:C.text,fontFamily:mono,fontSize:12,padding:"8px 12px",outline:"none",borderRadius:4}}
                />
                {isResponding ? (
                  <button type="button" onClick={handleStop}
                    style={{background:"rgba(255,68,85,0.15)",border:`1px solid ${C.red}`,color:C.red,fontFamily:mono,fontSize:11,padding:"0 16px",cursor:"pointer",borderRadius:4}}
                  >
                    ⏹ STOP
                  </button>
                ) : (
                  <button type="submit" disabled={!chatInput.trim()}
                    style={{background:"rgba(0,229,255,0.1)",border:`1px solid ${C.cyan}`,color:C.cyan,fontFamily:mono,fontSize:11,padding:"0 16px",cursor:"pointer",borderRadius:4}}
                  >
                    EXEC
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>

        {/* RIGHT: Modules + Globe (removed Network Uplink) */}
        <div style={{display:"flex",flexDirection:"column",gap:10,minHeight:0}}>
          <Panel title="Moduli Attivi" accent={C.purple} style={{flexShrink:0}}>
            {["Core Model (Llama3)","Audio Input (Whisper)","Speech Synthesis","Vector DB (Chroma)","Mainframe Sync"].map(m => (
              <div key={m} style={{display:"flex",justifyContent:"space-between",fontSize:10,padding:"4px 0",borderBottom:`1px solid ${C.cyanFaint}`}}>
                <span>{m}</span><span style={{color:C.green}}>ONLINE</span>
              </div>
            ))}
          </Panel>
          <Panel title="Processi" accent={C.cyan} style={{flex:1,fontSize:10}}>
            {metrics?.processes?.length ? metrics.processes.map(p => (
              <div key={p.pid} style={{display:"flex",justifyContent:"space-between",padding:"2px 0",fontSize:9,borderBottom:`1px solid ${C.cyanFaint}`}}>
                <span style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",flex:1}}>{p.name}</span>
                <span style={{color:C.cyan,flexShrink:0,marginLeft:4}}>{p.cpu}%</span>
              </div>
            )) : <span style={{color:C.textFaint}}>Nessun dato</span>}
          </Panel>
          <Panel title="Globe" accent={C.green} style={{flexShrink:0,padding:"4px 8px"}}>
            <GlobeImage />
          </Panel>
        </div>

      </div>
    </div>
  );
}
