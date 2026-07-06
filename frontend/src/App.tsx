import { useState, useEffect, useRef, useCallback, type FormEvent } from "react";
import { Canvas } from "@react-three/fiber";
import Sidebar from "./components/Sidebar";
import { ArcReactor3D } from "./components/ArcReactor3D";
import { MarkdownRenderer } from "./components/MarkdownRenderer";
import { Scanlines } from "./components/Scanlines";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { MetricBadge } from "./components/MetricBadge";
import { SystemLog } from "./components/SystemLog";
import { ConfirmModal } from "./components/ConfirmModal";
import MarketPanel from "./components/MarketPanel";
import VoiceVisualizer from "./components/VoiceVisualizer";
import HolographicDisplay from "./components/HolographicDisplay";
import { Waveform } from "./components/Waveform";
import { useStore } from "./hooks/useStore";
import { useWebSocket } from "./hooks/useWebSocket";
import { useWakeWord } from "./hooks/useWakeWord";
import { useAudioStream } from "./hooks/useAudioStream";
import { fetchFromBest, fetchWithAuth } from "./utils/fetch";
import { THEMES, C, setTheme as applyTheme, font, mono } from "./utils/theme";
import VectorViz from "./components/VectorViz";
import TypewriterText from "./components/TypewriterText";
import { API_URL, JARVIS_COLORS } from "./utils/constants";
import type { WSMessage } from "./types";

const HOST_METRICS_URL = "http://localhost:18765";

interface MetricSnapshot {
  cpu: number; ram: number; temp: number|null; disk: number;
  history: { cpu: number[]; ram: number[]; temp: number[]; disk: number[] };
  processes: {pid:number;name:string;cpu:number;mem:number}[];
  uptime: number; ram_gb: number; ram_total_gb: number; net_sent: number; net_recv: number;
}

export default function JarvisDashboard() {
  const [metrics, setMetrics] = useState<MetricSnapshot | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<{id:number;role:string;text:string;sources?:any[];commands?:string[]}[]>([
    {id:0,role:"system",text:"Sistemi ausiliari inizializzati. Reattore ARC stabile. In attesa di comandi, Signore."}
  ]);
  const [feedbackSent, setFeedbackSent] = useState<Record<number,number>>({});
  const [attachedFiles, setAttachedFiles] = useState<{name:string;content:string}[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [theme, setThemeState] = useState<"dark"|"light">("dark");
  const [activeTab, setActiveTab] = useState<"reactor" | "markets" | "log">("reactor");
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [pendingActionLabel, setPendingActionLabel] = useState<string>("");
  const [confirming, setConfirming] = useState(false);
  const [ctxMenu, setCtxMenu] = useState<{x:number;y:number;msg:{id:number;role:string;text:string}}|null>(null);
  const [authToken, setAuthToken] = useState<string|null>(() => {
    const t = localStorage.getItem("jwt_token");
    return t && t !== "null" && t !== "undefined" ? t : null;
  });
  const [authUser, setAuthUser] = useState<string|null>(() => {
    const u = localStorage.getItem("jwt_user");
    return u && u !== "null" && u !== "undefined" ? u : null;
  });
  const [authMode, setAuthMode] = useState<"login"|"register">("login");
  const [authForm, setAuthForm] = useState({username:"",password:""});
  const [authError, setAuthError] = useState("");
  const [showVectorViz, setShowVectorViz] = useState(false);
  const [timeStr, setTimeStr] = useState(new Date().toLocaleTimeString('it-IT'));
  const [ragThreshold, setRagThreshold] = useState(1.2);
  useEffect(() => {
    fetchWithAuth("/api/rag/threshold").then(r => r.ok && r.json()).then(d => { if (d?.threshold != null) setRagThreshold(d.threshold); }).catch(() => {});
  }, []);
  const updateRagThreshold = async (val: number) => {
    setRagThreshold(val);
    try { await fetchWithAuth("/api/rag/threshold", {method:"PUT", body:JSON.stringify({threshold:val})}); } catch {}
  };
  useEffect(() => { applyTheme(theme); }, [theme]);

  useEffect(() => {
    const handler = () => {
      setAuthToken(null);
      setAuthUser(null);
    };
    window.addEventListener("auth:expired", handler);
    return () => window.removeEventListener("auth:expired", handler);
  }, []);

  useEffect(() => {
    const t = localStorage.getItem("jwt_token");
    const u = localStorage.getItem("jwt_user");
    console.log("[AUTH] token:", t ? t.substring(0,20)+"..." : null, "user:", u);
  }, []);
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("[data-debug-reset]")) {
        localStorage.removeItem("jwt_token");
        localStorage.removeItem("jwt_user");
        window.location.reload();
      }
    };
    document.addEventListener("click", handler, true);
    return () => document.removeEventListener("click", handler, true);
  }, []);
  useEffect(() => { const id = setInterval(() => setTimeStr(new Date().toLocaleTimeString('it-IT')), 1000); return () => clearInterval(id); }, []);
  const msgIdRef = useRef(1);
  const chatEndRef = useRef<HTMLDivElement>(null!);
  const chatContainerRef = useRef<HTMLDivElement>(null!);
  const fileInputRef = useRef<HTMLInputElement>(null!);
  const abortRef = useRef<AbortController | null>(null);

  // ── Stato unificato vocale/testuale ──────────────────────────────────
  const storeStatus = useStore((s) => s.status);
  const storeVolume = useStore((s) => s.volume);
  const setStoreStatus = useStore((s) => s.setStatus);
  const setStoreVolume = useStore((s) => s.setVolume);
  const setStoreConnected = useStore((s) => s.setConnected);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [textResponding, setTextResponding] = useState(false);
  const listening = storeStatus === "listening";
  const isResponding = textResponding || storeStatus === "processing" || storeStatus === "speaking";

  // ── Hooks voce ───────────────────────────────────────────────────────
  // Ref ponte: useAudioStream chiama sendAudio da useWebSocket senza creare dipendenze
  const sendAudioRef = useRef<(data: ArrayBuffer) => void>(() => {});
  const startRecRef = useRef<() => void>(() => {});
  const stopRecRef = useRef<() => void>(() => {});

  const handleWSMessage = useCallback((msg: WSMessage) => {
    if (msg.type === "transcription") {
      const uid = msgIdRef.current++;
      setMessages((p) => [...p, { id: uid, role: "user", text: msg.text || "" }]);
      setStoreStatus("processing");
    } else if (msg.type === "response") {
      const rid = msgIdRef.current++;
      const m = msg as any;
      setMessages((p) => [...p, { id: rid, role: "system", text: m.text || "", sources: m.sources }]);
      setStoreStatus("speaking");
    } else if (msg.type === "speaking_end") {
      setStoreStatus("idle");
    } else if (msg.type === "error") {
      setStoreStatus("idle");
    }
  }, [setStoreStatus]);

  const { sendAudio } = useWebSocket({
    onMessage: handleWSMessage,
    onAudioData: useCallback((blob: Blob) => {
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => setStoreStatus("idle");
      audio.play().catch(() => setStoreStatus("idle"));
    }, [setStoreStatus]),
    onStatusChange: useCallback((connected: boolean) => setStoreConnected(connected), [setStoreConnected]),
  });
  sendAudioRef.current = sendAudio;

  const { startRecording, stopRecording } = useAudioStream({
    onAudioData: useCallback((data: ArrayBuffer) => sendAudioRef.current(data), []),
    onVolumeChange: useCallback((vol: number) => setStoreVolume(vol), [setStoreVolume]),
  });
  startRecRef.current = startRecording;
  stopRecRef.current = stopRecording;

  const handleWake = useCallback(() => {
    setStoreStatus("listening");
    startRecRef.current();
  }, [setStoreStatus]);

  const canWake = voiceEnabled && storeStatus === "idle" && !textResponding;
  useWakeWord({ onWake: handleWake, enabled: canWake });

  const toggleVoice = useCallback(() => {
    setVoiceEnabled((v) => {
      if (v) { stopRecRef.current(); setStoreStatus("idle"); }
      return !v;
    });
  }, [setStoreStatus]);

  const { activeSessionId, chatHistory, setChatHistory, addChatHistory } = useStore();

  // Validate session existence
  useEffect(() => {
    if (activeSessionId) {
      fetchWithAuth(`/api/chats/${activeSessionId}`).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      }).catch(() => {
        setChatHistory([]);
        localStorage.removeItem('activeSessionId');
        if (!messages.find(m => m.text.includes("Sessione scaduta"))) {
          setMessages(p => [...p, {id:msgIdRef.current++,role:"system",text:"⚠️ Sessione scaduta o non valida. Nuova sessione avviata."}]);
        }
      });
    }
  }, [activeSessionId, setChatHistory]);

  const sendFeedback = async (msgId:number, rating:number, userMsg:string, assistantMsg:string) => {
    if (feedbackSent[msgId]) return;
    try {
      await fetchWithAuth(`/api/feedback`, {
        method:"POST",
        body:JSON.stringify({message_id:String(msgId),user_message:userMsg,assistant_response:assistantMsg,rating,language:"it",intent:"chat"}),
      });
      setFeedbackSent(p => ({...p, [msgId]:rating}));
    } catch {}
  };

  const exportChat = async (fmt: "txt" | "pdf") => {
    const msgs = displayMessages.map(m => ({role: m.role, text: m.text}));
    if (fmt === "txt") {
      const txt = msgs.map(m => `${m.role === "user" ? "TU" : "J.A.R.V.I.S."}: ${m.text}`).join("\n\n---\n\n");
      const blob = new Blob([txt], {type:"text/plain;charset=utf-8"});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `jarvis-${new Date().toISOString().slice(0,10)}.txt`; a.click();
      URL.revokeObjectURL(url);
    } else {
      try {
        const r = await fetchWithAuth(`/api/export/pdf`, {method:"POST", body:JSON.stringify({messages:msgs,format:"pdf"})});
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a"); a.href = url; a.download = `jarvis-${new Date().toISOString().slice(0,10)}.pdf`; a.click();
        URL.revokeObjectURL(url);
      } catch (err) { console.error("PDF export fallito:", err); }
    }
  };

  const fetchMetrics = useCallback(async () => {
    let d = await fetchFromBest([`${HOST_METRICS_URL}/api/system/metrics`], 2000);
    if (!d) {
      try { const r = await fetchWithAuth(`/api/system/metrics`); if (r.ok) d = await r.json(); } catch {}
    }
    if (d) setMetrics(d as MetricSnapshot);
  }, []);

  useEffect(() => { fetchMetrics(); const id = setInterval(fetchMetrics, 5000); return () => clearInterval(id); }, [fetchMetrics]);

  const uploadFile = async (file: File) => {
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await fetchWithAuth(`/api/upload`, {method:"POST", body:fd});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setAttachedFiles(p => [...p, {name:d.filename, content:d.content}]);
    } catch (err) {
      console.error("Upload fallito:", err);
    } finally {
      setUploading(false);
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
      const r = await fetchWithAuth(`/api/confirm`, {
        method:"POST",
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
    setTextResponding(false);
    if (storeStatus === "speaking" || storeStatus === "processing") {
      setStoreStatus("idle");
    }
  };

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    try {
      const r = await fetch(`/api/auth/${authMode}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(authForm)});
      const d = await r.json();
      if (!r.ok) { setAuthError(d.detail || "Auth failed"); return; }
      localStorage.setItem("jwt_token", d.access_token);
      localStorage.setItem("jwt_user", d.username);
      setAuthToken(d.access_token);
      setAuthUser(d.username);
    } catch (err) { setAuthError("Connection error"); }
  };

  const handleLogout = () => {
    localStorage.removeItem("jwt_token");
    localStorage.removeItem("jwt_user");
    setAuthToken(null);
    setAuthUser(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape" && isResponding) {
      e.preventDefault();
      handleStop();
    }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      const form = (e.target as HTMLElement).closest("form");
      form?.requestSubmit();
    }
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
    setTextResponding(true);

    let sid = 0;
    let sessionIdReturned: number | null = null;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    abortRef.current = controller;
    try {
      const r = await fetchWithAuth(`/api/chat`, {
        method:"POST",
        body:JSON.stringify({text:userMsg, file_content: fileContent, session_id: activeSessionId ?? undefined, stream: true}),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      abortRef.current = null;
      if (!r.ok) throw new Error(`HTTP ${r.status}`);

      const reader = r.body?.getReader();
      if (!reader) { setTextResponding(false); return; }
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
        const sr = await fetchWithAuth(`${API_URL}/chats`);
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
    setTextResponding(false);
  };

  useEffect(() => {
    // Smart scroll: only if user is near bottom (within 100px)
    const container = chatContainerRef.current;
    if (container) {
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
      if (isNearBottom) {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    } else {
      // Fallback if container ref not set yet
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  useEffect(() => { if (!ctxMenu) return; const close = () => setCtxMenu(null); window.addEventListener("click", close); return () => window.removeEventListener("click", close); }, [ctxMenu]);

  const copyToClipboard = async (text: string) => { try { await navigator.clipboard.writeText(text); } catch {} };

  const displayMessages = activeSessionId && chatHistory.length > 0
    ? [{id:0,role:"system",text:"Sistemi ausiliari inizializzati."}, ...chatHistory.map((m,i) => ({id:i+1,role:m.role,text:m.content}))]
    : messages;

  return (
    <div style={{background:C.bg,height:"100vh",width:"100vw",overflow:"hidden",fontFamily:font,color:C.text,position:"relative",display:"flex",flexDirection:"column",boxSizing:"border-box"}}>
      <Scanlines theme={theme} />



      {/* ── Ologramma compatto nella toolbar ── */}
      {voiceEnabled && (
        <div style={{position:"fixed",top:50,right:14,zIndex:200,width:80,height:80,pointerEvents:"none"}}>
          <Canvas camera={{position:[0,0,6],fov:50}}>
            <HolographicDisplay />
          </Canvas>
        </div>
      )}

      {/* ── VoiceVisualizer overlay nel tab reattore ── */}
      {(storeStatus === "listening" || storeStatus === "speaking") && (
        <div style={{position:"fixed",bottom:100,left:"50%",transform:"translateX(-50%)",width:"60%",maxWidth:500,height:80,zIndex:150,pointerEvents:"none"}}>
          <Canvas camera={{position:[0,0,5],fov:50}}>
            <VoiceVisualizer />
          </Canvas>
        </div>
      )}

      <div style={{flexShrink:0,display:"flex",alignItems:"center",gap:10,padding:"6px 14px",borderBottom:`1px solid ${C.border}`,background:C.bgPanel}}>
        <div style={{flexShrink:0,marginRight:4,display:"flex",alignItems:"center",gap:6}}>
          <span style={{fontSize:15,letterSpacing:"0.3em",color:C.cyan,fontWeight:"bold",fontFamily:mono}}>J.A.R.V.I.S</span>
          {voiceEnabled && (
            <span style={{
              fontSize:9,fontFamily:mono,letterSpacing:"0.1em",
              color: listening ? C.green : storeStatus === "processing" ? C.amber : C.cyan,
              background: (listening||storeStatus!=="idle") ? `${C.cyan}15` : "transparent",
              padding:"1px 6px",borderRadius:3,border:`1px solid ${listening?C.green:storeStatus!=="idle"?C.cyan:"transparent"}`,
              transition:"all 0.3s",
            }}>
              {listening ? "ASCOLTO" : storeStatus === "processing" ? "ELABORAZIONE" : storeStatus === "speaking" ? "VOCE" : "VOCALE"}
            </span>
          )}
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
          <span onClick={()=>exportChat("txt")}
            style={{cursor:"pointer",fontSize:14,color:C.textDim}}
            title="Esporta come TXT">📄</span>
          <span onClick={()=>exportChat("pdf")}
            style={{cursor:"pointer",fontSize:14,color:C.textDim}}
            title="Esporta come PDF">📕</span>
          <span onClick={()=>setShowVectorViz(true)}
            style={{cursor:"pointer",fontSize:13,color:C.textDim}}
            title="Visualizzazione vettori">📊</span>
          <label style={{display:"flex",alignItems:"center",gap:4,fontSize:11,cursor:"pointer",color:C.textFaint}} title="Soglia similarità RAG">
            RAG
            <input type="range" min="0.1" max="3.0" step="0.1" value={ragThreshold}
              onChange={e=>updateRagThreshold(parseFloat(e.target.value))}
              style={{width:60,height:4,accentColor:C.cyan,verticalAlign:"middle",cursor:"pointer"}} />
            <span style={{minWidth:28,textAlign:"right",fontFamily:mono}}>{ragThreshold.toFixed(1)}</span>
          </label>
          {authUser && <span style={{fontSize:11,color:C.green,fontFamily:mono}}>{authUser}</span>}
          {authUser && <span onClick={handleLogout} style={{cursor:"pointer",fontSize:13,color:C.textFaint}} title="Logout">🚪</span>}
          <span data-debug-reset="1" onClick={()=>{localStorage.removeItem("jwt_token");localStorage.removeItem("jwt_user");setAuthToken(null);setAuthUser(null);}} style={{cursor:"pointer",fontSize:11,color:C.amber,border:`1px solid ${C.amber}30`,padding:"2px 6px",borderRadius:3,fontFamily:mono,position:"relative",zIndex:9999}} title="Reset autenticazione forzato">🔓 Reset</span>
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
                  {isResponding && displayMessages.filter(m=>m.role==="system").every(m => m.text) && (
                    <div style={{alignSelf:"flex-start",background:"rgba(0,255,136,0.03)",borderLeft:`2px solid ${C.green}`,padding:"5px 10px",borderRadius:4,fontSize:13,color:C.textDim,fontFamily:mono,display:"flex",alignItems:"center",gap:6}}>
                      <span style={{fontSize:14,animation:"blink 1.2s ease-in-out infinite"}}>●</span> J.A.R.V.I.S. sta pensando...
                    </div>
                  )}
                  {displayMessages.slice(1).map((msg,i,arr) => {
                    const prevUser = msg.role==="system" ? arr.slice(0,i).reverse().find(m => m.role==="user") : null;
                    return (
                    <div key={msg.id} onContextMenu={e => { e.preventDefault(); setCtxMenu({x:e.clientX,y:e.clientY,msg}); }}
                      style={{
                      alignSelf: msg.role==="user" ? "flex-end" : "flex-start",
                      background: msg.role==="user" ? C.cyanFaint : "rgba(0,255,136,0.05)",
                      borderLeft: msg.role==="system" ? `2px solid ${C.green}` : "none",
                      borderRight: msg.role==="user" ? `2px solid ${C.cyan}` : "none",
                      padding:"5px 10px",borderRadius:4,maxWidth:"85%",fontSize:14,lineHeight:1.5,position:"relative",cursor:"context-menu",
                    }}>
                      <span style={{fontSize:10,color:msg.role==="user"?C.cyan:C.green,display:"block",marginBottom:1,fontFamily:mono,letterSpacing:"0.05em"}}>
                        {msg.role==="user" ? "TU" : "J.A.R.V.I.S."}
                      </span>
                      {msg.role === "system" ? (
                        isResponding && i === arr.length - 1 ? (
                          <span><TypewriterText text={msg.text} speed={8} /></span>
                        ) : (
                          <MarkdownRenderer content={msg.text} />
                        )
                      ) : msg.text}
                      {msg.role==="system" && prevUser && (
                        <div style={{display:"flex",gap:4,marginTop:4}}>
                          <span onClick={() => !feedbackSent[msg.id] && sendFeedback(msg.id,2,prevUser.text,msg.text)}
                            style={{cursor:feedbackSent[msg.id]?"default":"pointer",fontSize:14,color:feedbackSent[msg.id]===2?C.green:C.textFaint,opacity:feedbackSent[msg.id]?0.4:0.6,transition:"all 0.3s"}}>
                            {feedbackSent[msg.id]===2?"✓":feedbackSent[msg.id]?"":"▲"}
                          </span>
                          <span onClick={() => !feedbackSent[msg.id] && sendFeedback(msg.id,1,prevUser.text,msg.text)}
                            style={{cursor:feedbackSent[msg.id]?"default":"pointer",fontSize:14,color:feedbackSent[msg.id]===1?C.red:C.textFaint,opacity:feedbackSent[msg.id]?0.4:0.6,transition:"all 0.3s"}}>
                            {feedbackSent[msg.id]===1?"✓":feedbackSent[msg.id]?"":"▼"}
                          </span>
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

                {(attachedFiles.length > 0 || uploading) && (
                  <div style={{flexShrink:0,display:"flex",gap:6,flexWrap:"wrap"}}>
                    {attachedFiles.map((f,i) => (
                      <span key={i} style={{fontSize:13,fontFamily:mono,background:"rgba(0,229,255,0.12)",border:`1px solid ${C.cyan}`,borderRadius:4,padding:"3px 10px",display:"flex",alignItems:"center",gap:6,color:C.cyan,boxShadow:"0 0 8px rgba(0,229,255,0.12)"}}>
                        <span style={{fontSize:15}}>📎</span> {f.name}
                        <span onClick={()=>removeFile(i)} style={{cursor:"pointer",color:C.red,fontSize:16,lineHeight:"14px",fontWeight:"bold",marginLeft:2,opacity:0.8}} title="Rimuovi">×</span>
                      </span>
                    ))}
                    {uploading && (
                      <span style={{fontSize:13,fontFamily:mono,background:"rgba(0,229,255,0.08)",border:`1px solid ${C.cyanFaint}`,borderRadius:4,padding:"3px 10px",display:"flex",alignItems:"center",gap:6,color:C.textDim}}>
                        <span style={{fontSize:15,animation:"spin 0.8s linear infinite",display:"inline-block"}}>⟳</span> Caricamento...
                      </span>
                    )}
                  </div>
                )}
                </>
              )}

              <div style={{flexShrink:0,display:"flex",gap:8,alignItems:"center"}}>
                <button onClick={toggleVoice} style={{width:36,height:36,borderRadius:"50%",background:voiceEnabled?C.cyanFaint:"transparent",border:`1px solid ${voiceEnabled?C.cyan:C.border}`,color:voiceEnabled?C.cyan:C.textDim,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,fontSize:14,position:"relative"}}>
                  {voiceEnabled ? (listening ? "●" : "◉") : "🎤"}
                  {voiceEnabled && !listening && storeStatus === "idle" && (
                    <span style={{position:"absolute",top:-2,right:-2,width:8,height:8,borderRadius:"50%",background:C.green,opacity:0.8}} />
                  )}
                </button>
                <div style={{flex:1,background:C.bgPanel,border:`1px solid ${C.border}`,borderRadius:16,padding:"0 12px",height:32,display:"flex",alignItems:"center"}}>
                  <Waveform active={voiceEnabled||isResponding} color={isResponding?C.green:voiceEnabled?C.cyan:C.textDim} />
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
                  onKeyDown={handleKeyDown}
                  placeholder="Invia una direttiva testuale a J.A.R.V.I.S... (Ctrl+Enter per inviare, Esc per stop)"
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

      {/* ── Auth Modal ── */}
      {!authToken && (
        <div style={{position:"fixed",inset:0,zIndex:9998,background:"#0a1e30",display:"flex",alignItems:"center",justifyContent:"center"}}>
          <form onSubmit={handleAuth} style={{background:"#0f2a40",border:"1px solid rgba(0,229,255,0.35)",borderRadius:8,padding:"30px 40px",width:360,boxShadow:"0 0 60px rgba(0,229,255,0.15)"}}>
            <div style={{textAlign:"center",marginBottom:6,fontFamily:mono,fontSize:12,letterSpacing:"0.2em",color:C.textFaint}}>AUTENTICAZIONE RICHIESTA</div>
            <div style={{textAlign:"center",marginBottom:20,fontFamily:mono,fontSize:22,letterSpacing:"0.3em",color:C.cyan,fontWeight:"bold"}}>J.A.R.V.I.S.</div>
            <div style={{display:"flex",gap:0,marginBottom:16}}>
              <button type="button" onClick={()=>setAuthMode("login")} style={{flex:1,padding:"6px 0",background:authMode==="login"?C.cyanFaint:"transparent",border:`1px solid ${authMode==="login"?C.cyan:"transparent"}`,color:authMode==="login"?C.cyan:C.textDim,borderRadius:"4px 0 0 4px",cursor:"pointer",fontSize:13}}>Accedi</button>
              <button type="button" onClick={()=>setAuthMode("register")} style={{flex:1,padding:"6px 0",background:authMode==="register"?C.cyanFaint:"transparent",border:`1px solid ${authMode==="register"?C.cyan:"transparent"}`,color:authMode==="register"?C.cyan:C.textDim,borderRadius:"0 4px 4px 0",cursor:"pointer",fontSize:13}}>Registrati</button>
            </div>
            <input type="text" placeholder="Username" value={authForm.username} onChange={e=>setAuthForm(p=>({...p,username:e.target.value}))}
              style={{width:"100%",padding:"8px 10px",marginBottom:8,background:"rgba(0,0,0,0.3)",border:"1px solid rgba(0,229,255,0.2)",borderRadius:4,color:C.text,fontSize:14,outline:"none"}} />
            <input type="password" placeholder="Password" value={authForm.password} onChange={e=>setAuthForm(p=>({...p,password:e.target.value}))}
              style={{width:"100%",padding:"8px 10px",marginBottom:12,background:"rgba(0,0,0,0.3)",border:"1px solid rgba(0,229,255,0.2)",borderRadius:4,color:C.text,fontSize:14,outline:"none"}} />
            {authError && <div style={{color:C.red,fontSize:12,marginBottom:8,fontFamily:mono}}>⚠ {authError}</div>}
            <button type="submit" style={{width:"100%",padding:"9px 0",background:C.cyanFaint,border:`1px solid ${C.cyan}40`,borderRadius:4,color:C.cyan,cursor:"pointer",fontSize:14,fontFamily:mono,fontWeight:"bold",letterSpacing:"0.1em"}}>
              {authMode === "login" ? "► ACCEDI" : "► REGISTRATI"}
            </button>
          </form>
        </div>
      )}

      {pendingActionId && (
        <ConfirmModal
          pendingActionLabel={pendingActionLabel}
          confirming={confirming}
          onConfirm={handleConfirm}
        />
      )}

      {ctxMenu && (
        <div style={{position:"fixed",top:0,left:0,right:0,bottom:0,zIndex:9999}} onClick={()=>setCtxMenu(null)}>
          <div style={{position:"absolute",top:ctxMenu.y,left:ctxMenu.x,background:"#111",border:"1px solid #333",borderRadius:6,boxShadow:"0 4px 20px rgba(0,0,0,0.6)",padding:"4px 0",minWidth:160,zIndex:10000,fontSize:13,fontFamily:mono}}
            onClick={e=>e.stopPropagation()}>
            <div onClick={()=>{copyToClipboard(ctxMenu.msg.text);setCtxMenu(null);}}
              style={{padding:"6px 14px",cursor:"pointer",color:"#ccc",display:"flex",alignItems:"center",gap:8}}
              onMouseEnter={e=>e.currentTarget.style.background="#222"} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
              📋 Copia testo
            </div>
            <div onClick={()=>{copyToClipboard(ctxMenu.msg.text);const blob=new Blob([ctxMenu.msg.text],{type:"text/plain;charset=utf-8"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`messaggio-${ctxMenu.msg.id}.txt`;a.click();URL.revokeObjectURL(url);setCtxMenu(null);}}
              style={{padding:"6px 14px",cursor:"pointer",color:"#ccc",display:"flex",alignItems:"center",gap:8}}
              onMouseEnter={e=>e.currentTarget.style.background="#222"} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
              📥 Esporta messaggio
            </div>
          </div>
        </div>
      )}

      {showVectorViz && <VectorViz onClose={()=>setShowVectorViz(false)} />}
    </div>
  );
}
