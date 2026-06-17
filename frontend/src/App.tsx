import { useState, useEffect, useRef, useCallback, type FormEvent } from "react";
import Sidebar from "./components/Sidebar";
import { ArcReactor3D } from "./components/ArcReactor3D";
import { MarkdownRenderer } from "./components/MarkdownRenderer";
import { Scanlines } from "./components/Scanlines";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { MetricBadge } from "./components/MetricBadge";
import { SystemLog } from "./components/SystemLog";
import { Waveform } from "./components/Waveform";
import { ConfirmModal } from "./components/ConfirmModal";
import MarketPanel from "./components/MarketPanel";
import { useStore } from "./hooks/useStore";
import { fetchFromBest } from "./utils/fetch";
import { THEMES, C, setTheme as applyTheme, font, mono } from "./utils/theme";
import { API_URL } from "./utils/constants";

const HOST_METRICS_URL = "http://localhost:18765";
const DOCKER_API = "";

interface MetricSnapshot {
  cpu: number; ram: number; temp: number|null; disk: number;
  history: { cpu: number[]; ram: number[]; temp: number[]; disk: number[] };
  processes: {pid:number;name:string;cpu:number;mem:number}[];
  uptime: number; ram_gb: number; ram_total_gb: number; net_sent: number; net_recv: number;
}

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
  const [theme, setThemeState] = useState<"dark"|"light">("dark");
  const [activeTab, setActiveTab] = useState<"reactor" | "markets" | "log">("reactor");
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [pendingActionLabel, setPendingActionLabel] = useState<string>("");
  const [confirming, setConfirming] = useState(false);
  const [timeStr, setTimeStr] = useState(new Date().toLocaleTimeString('it-IT'));
  useEffect(() => { applyTheme(theme); }, [theme]);
  useEffect(() => { const id = setInterval(() => setTimeStr(new Date().toLocaleTimeString('it-IT')), 1000); return () => clearInterval(id); }, []);
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

  const handleConfirm = async (confirm: boolean) => {
    if (!pendingActionId) return;
    setConfirming(true);
    try {
      const r = await fetch(`${DOCKER_API}/api/confirm`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({action_id: pendingActionId, confirm}),
      });
      const d = await r.json();
      const mid = msgIdRef.current++;
      if (confirm && d.status === "ok") {
        setMessages(p => [...p, {id:mid, role:"system", text: `✅ Azione eseguita: ${d.result}`}]);
      } else if (!confirm || d.status === "cancelled") {
        setMessages(p => [...p, {id:mid, role:"system", text: `❌ Azione annullata.`}]);
      } else {
        setMessages(p => [...p, {id:mid, role:"system", text: `⚠️ Errore: ${d.message}`}]);
      }
    } catch (err) {
      const mid = msgIdRef.current++;
      setMessages(p => [...p, {id:mid, role:"system", text: `⚠️ Errore conferma: ${(err as Error)?.message}`}]);
    }
    setPendingActionId(null);
    setPendingActionLabel("");
    setConfirming(false);
  };

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
              if (ev.pending_action) {
                setPendingActionId(ev.pending_action);
                setPendingActionLabel("azione sistema");
              }
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
      <Scanlines theme={theme} />

      <div style={{flexShrink:0,display:"flex",alignItems:"center",gap:10,padding:"6px 14px",borderBottom:`1px solid ${C.border}`,background:C.bgPanel}}>
        <div style={{flexShrink:0,marginRight:4}}>
          <span style={{fontSize:15,letterSpacing:"0.3em",color:C.cyan,fontWeight:"bold",fontFamily:mono}}>J.A.R.V.I.S</span>
        </div>
        <MetricBadge label="CPU" value={Math.round(cpu)} unit="%" color={C.cyan} history={cpuHist} />
        <MetricBadge label="RAM" value={Math.round(ram)} unit="%" color={C.green} history={ramHist} />
        <MetricBadge label="TEMP" value={temp ? Math.round(temp) : "—"} unit="°C" color={C.amber} history={tempHist} />
        <MetricBadge label="DISK" value={Math.round(disk)} unit="%" color={C.text} />
        <div style={{flex:1,minWidth:0,display:"flex",alignItems:"center",paddingLeft:8}}>
          <SystemLog compact />
        </div>
        <div style={{fontFamily:mono,fontSize:13,color:C.textFaint,flexShrink:0,display:"flex",alignItems:"center",gap:10}}>
          <span onClick={()=>setThemeState(t=>t==="dark"?"light":"dark")}
            style={{cursor:"pointer",fontSize:16,color:C.amber,transition:"transform 0.2s"}}
            title="Cambia tema">{theme==="dark"?"☀️":"🌙"}</span>
          <span onClick={exportChat}
            style={{cursor:"pointer",fontSize:14,color:C.textDim}}
            title="Esporta conversazione">📥</span>
          {timeStr}
        </div>
      </div>

      <div style={{flex:1,display:"grid",gridTemplateColumns:"240px 1fr",gap:0,minHeight:0}}>
        <div style={{overflow:"hidden",borderRight:`1px solid ${C.border}`}}>
          <Sidebar />
        </div>

        <div style={{display:"flex",flexDirection:"column",minHeight:0,padding:"8px 10px",gap:6}}>
          <div style={{flexShrink:0,display:"flex",gap:2}}>
            {([["reactor","⚛ Reattore"],["markets","📈 Mercati"],["log","📋 Log"]] as const).map(([key,label]) => (
              <button key={key} onClick={()=>setActiveTab(key)}
                style={{fontSize:13,fontFamily:mono,background:activeTab===key?C.cyanFaint:"transparent",border:`1px solid ${activeTab===key?C.cyan:C.border}`,color:activeTab===key?C.cyan:C.textDim,borderRadius:"3px 3px 0 0",padding:"5px 16px",cursor:"pointer",borderBottom:activeTab===key?`1px solid ${C.bgPanel}`:"none",marginBottom:-1}}>{label}</button>
            ))}
          </div>

          {/* ── REATTORE: reactor + chat ── */}
          {activeTab === "reactor" && (
            <div style={{flex:1,display:"flex",flexDirection:"column",minHeight:0,gap:6}}>
              {displayMessages.length > 1 ? (
                <div style={{flexShrink:0,width:80,height:80,marginLeft:"auto"}}>
                  <ErrorBoundary fallback={<div style={{width:80,height:80,display:"flex",alignItems:"center",justifyContent:"center",color:C.textDim,fontFamily:mono,fontSize:9}}>3D</div>}>
                    <ArcReactor3D isResponding={isResponding} />
                  </ErrorBoundary>
                </div>
              ) : (
                <div style={{flex:1,background:"rgba(0,0,0,0.2)",borderRadius:4,border:`1px solid ${C.cyanFaint}`,overflow:"hidden",position:"relative",minHeight:120}}>
                  <ErrorBoundary fallback={<div style={{padding:20,color:C.textDim,fontFamily:mono,fontSize:12}}>3D non disponibile</div>}>
                    <ArcReactor3D isResponding={isResponding} />
                  </ErrorBoundary>
                </div>
              )}

              {displayMessages.length > 1 && (
                <>
                <div ref={chatContainerRef}
                  onDragOver={e=>{e.preventDefault();setDragOver(true);}}
                  onDragLeave={()=>setDragOver(false)}
                  onDrop={handleDrop}
                  style={{flex:1,overflowY:"auto",display:"flex",flexDirection:"column",gap:4,padding:"6px 8px",background:dragOver?"rgba(0,229,255,0.08)":"rgba(0,0,0,0.15)",borderRadius:4,border:`1px solid ${dragOver?C.cyan:C.cyanFaint}`,transition:"background 0.15s, border-color 0.15s"}}>
                  {displayMessages.slice(1).map((msg,i,arr) => {
                    const prevUser = msg.role==="system" ? arr.slice(0,i).reverse().find(m => m.role==="user") : null;
                    return (
                    <div key={msg.id} style={{
                      alignSelf: msg.role==="user" ? "flex-end" : "flex-start",
                      background: msg.role==="user" ? C.cyanFaint : "rgba(0,255,136,0.05)",
                      borderLeft: msg.role==="system" ? `2px solid ${C.green}` : "none",
                      borderRight: msg.role==="user" ? `2px solid ${C.cyan}` : "none",
                      padding:"5px 10px",borderRadius:4,maxWidth:"85%",fontSize:14,lineHeight:1.5,position:"relative",
                    }}>
                      <span style={{fontSize:10,color:msg.role==="user"?C.cyan:C.green,display:"block",marginBottom:1,fontFamily:mono,letterSpacing:"0.05em"}}>
                        {msg.role==="user" ? "TU" : "J.A.R.V.I.S."}
                      </span>
                      {msg.role === "system" ? <MarkdownRenderer content={msg.text} /> : msg.text}
                      {msg.role==="system" && prevUser && (
                        <div style={{display:"flex",gap:4,marginTop:4}}>
                          <span onClick={() => sendFeedback(msg.id,2,prevUser.text,msg.text)}
                            style={{cursor:"pointer",fontSize:14,color:feedbackSent[msg.id]===2?C.green:C.textFaint,opacity:0.6}}>▲</span>
                          <span onClick={() => sendFeedback(msg.id,1,prevUser.text,msg.text)}
                            style={{cursor:"pointer",fontSize:14,color:feedbackSent[msg.id]===1?C.red:C.textFaint,opacity:0.6}}>▼</span>
                        </div>
                      )}
                      {(msg as any).sources?.length > 0 && (
                        <div style={{marginTop:4,display:"flex",gap:6,flexWrap:"wrap"}}>
                          {(msg as any).sources.map((s:any,i:number) => (
                            <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
                              style={{fontSize:11,fontFamily:"'JetBrains Mono','Consolas',monospace",color:"#00e5ff",textDecoration:"none",border:"1px solid rgba(0,229,255,0.25)",borderRadius:3,padding:"1px 6px",opacity:0.7}}
                              title={s.url}>📰 {s.title}</a>
                          ))}
                        </div>
                      )}
                    </div>
                    );
                  })}
                  <div ref={chatEndRef} />
                </div>

                {attachedFiles.length > 0 && (
                  <div style={{flexShrink:0,display:"flex",gap:6,flexWrap:"wrap"}}>
                    {attachedFiles.map((f,i) => (
                      <span key={i} style={{fontSize:13,fontFamily:mono,background:"rgba(0,229,255,0.12)",border:`1px solid ${C.cyan}`,borderRadius:4,padding:"3px 10px",display:"flex",alignItems:"center",gap:6,color:C.cyan,boxShadow:"0 0 8px rgba(0,229,255,0.12)"}}>
                        <span style={{fontSize:15}}>📎</span> {f.name}
                        <span onClick={()=>removeFile(i)} style={{cursor:"pointer",color:C.red,fontSize:16,lineHeight:"14px",fontWeight:"bold",marginLeft:2,opacity:0.8}} title="Rimuovi">×</span>
                      </span>
                    ))}
                  </div>
                )}
                </>
              )}

              <div style={{flexShrink:0,display:"flex",gap:8,alignItems:"center"}}>
                <button onClick={()=>setListening(!listening)} style={{width:36,height:36,borderRadius:"50%",background:listening?C.cyanFaint:"transparent",border:`1px solid ${listening?C.cyan:C.border}`,color:listening?C.cyan:C.textDim,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,fontSize:14}}>
                  {listening ? "●" : "🎤"}
                </button>
                <div style={{flex:1,background:C.bgPanel,border:`1px solid ${C.border}`,borderRadius:16,padding:"0 12px",height:32,display:"flex",alignItems:"center"}}>
                  <Waveform active={listening||isResponding} color={isResponding?C.green:C.cyan} />
                </div>
              </div>

              <form onSubmit={handleSubmit} style={{flexShrink:0,display:"flex",gap:6,alignItems:"center"}}>
                <input type="file" ref={fileInputRef} onChange={handleFilePick} style={{display:"none"}} multiple />
                <button type="button" onClick={()=>fileInputRef.current?.click()}
                  style={{width:40,height:40,flexShrink:0,background:"rgba(0,229,255,0.08)",border:`1px solid ${C.cyan}`,color:C.cyan,cursor:"pointer",borderRadius:4,display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,boxShadow:"0 0 6px rgba(0,229,255,0.15)",transition:"background 0.15s"}}
                  title="Allega file (docx, xlsx, pdf, codice...)"
                  onMouseEnter={e=>(e.currentTarget.style.background="rgba(0,229,255,0.18)")}
                  onMouseLeave={e=>(e.currentTarget.style.background="rgba(0,229,255,0.08)")}
                >📎</button>
                <input type="text" value={chatInput} onChange={e=>setChatInput(e.target.value)}
                  placeholder="Invia una direttiva testuale a J.A.R.V.I.S..."
                  disabled={isResponding}
                  style={{flex:1,background:"rgba(0,0,0,0.25)",border:`1px solid ${C.border}`,color:C.text,fontFamily:font,fontSize:15,padding:"9px 14px",outline:"none",borderRadius:4}}
                />
                {isResponding ? (
                  <button type="button" onClick={handleStop}
                    style={{background:"rgba(255,68,85,0.15)",border:`1px solid ${C.red}`,color:C.red,fontFamily:mono,fontSize:13,padding:"0 16px",height:38,cursor:"pointer",borderRadius:4}}
                  >⏹ STOP</button>
                ) : (
                  <button type="submit" disabled={!chatInput.trim() && attachedFiles.length === 0}
                    style={{background:"rgba(0,229,255,0.1)",border:`1px solid ${C.cyan}`,color:C.cyan,fontFamily:mono,fontSize:13,padding:"0 16px",height:38,cursor:"pointer",borderRadius:4}}
                  >EXEC</button>
                )}
              </form>
            </div>
          )}

          {/* ── MERCATI: solo mercati ── */}
          {activeTab === "markets" && (
            <div style={{flex:1,background:"rgba(0,0,0,0.2)",borderRadius:4,border:`1px solid ${C.cyanFaint}`,overflow:"hidden",minHeight:120}}>
              <MarketPanel />
            </div>
          )}

          {/* ── LOG: solo log ── */}
          {activeTab === "log" && (
            <div style={{flex:1,background:"rgba(0,0,0,0.15)",borderRadius:4,border:`1px solid ${C.cyanFaint}`,overflow:"auto",padding:"4px 8px",minHeight:120}}>
              <SystemLog />
            </div>
          )}
        </div>
      </div>

      {pendingActionId && (
        <ConfirmModal
          pendingActionLabel={pendingActionLabel}
          confirming={confirming}
          onConfirm={handleConfirm}
        />
      )}
    </div>
  );
}
