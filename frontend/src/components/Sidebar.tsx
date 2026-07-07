import { useEffect, useState } from "react";
import { useStore } from "../hooks/useStore";
import { API_URL } from "../utils/constants";
import { fetchWithAuth } from "../utils/fetch";

const C = {
  bg: "#071520",
  panel: "#0a1e30",
  border: "rgba(0,229,255,0.18)",
  cyan: "#00e5ff",
  cyanFaint: "rgba(0,229,255,0.08)",
  textDim: "rgba(200,238,248,0.6)",
  textFaint: "rgba(200,238,248,0.3)",
  text: "#c8eef8",
  green: "#00ff88",
};

const STT_MODELS = ["tiny", "base", "small", "medium"];
const LANGUAGES = ["auto", "it", "en", "fr", "de", "es"];
const TTS_ENGINES = ["kokoro", "edge-tts"];

export default function Sidebar() {
  const { sessions, activeSessionId, setActiveSessionId, setSessions, addSession, removeSession, updateSession, setChatHistory } = useStore();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [vs, setVs] = useState<Record<string,any>>({});
  const [vsDirty, setVsDirty] = useState(false);

  useEffect(() => {
    fetchWithAuth(`${API_URL}/voice/settings`).then(r => r.ok && r.json()).then(d => { if (d) setVs(d); }).catch(() => {});
  }, []);

  const updateVs = (key: string, val: any) => {
    setVs((p: any) => ({...p, [key]: val}));
    setVsDirty(true);
  };

  const saveVs = async () => {
    try {
      await fetchWithAuth(`${API_URL}/voice/settings`, {method:"PUT", body:JSON.stringify(vs)});
      setVsDirty(false);
    } catch {}
  };

  useEffect(() => {
    fetchWithAuth(`${API_URL}/chats`)
      .then((r) => r.json())
      .then((d) => { if (d.sessions) setSessions(d.sessions); })
      .catch(() => {});
  }, []);

  const handleNew = async () => {
    try {
      const r = await fetchWithAuth(`${API_URL}/chats`, { method: "POST" });
      const d = await r.json();
      if (d.session) {
        addSession(d.session);
        setActiveSessionId(d.session.id);
        setChatHistory([]);
      }
    } catch {}
  };

  const handleSelect = async (id: number) => {
    setActiveSessionId(id);
    try {
      const r = await fetchWithAuth(`${API_URL}/chats/${id}/messages`);
      const d = await r.json();
      if (d.messages) setChatHistory(d.messages);
    } catch {}
  };

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      await fetchWithAuth(`${API_URL}/chats/${id}`, { method: "DELETE" });
      removeSession(id);
      if (activeSessionId === id) setChatHistory([]);
    } catch {}
  };

  const handleRename = async (id: number) => {
    if (editTitle.trim()) {
      try {
        await fetchWithAuth(`${API_URL}/chats/${id}`, { method: "PATCH", body: JSON.stringify({ title: editTitle.trim() }) });
        updateSession(id, { title: editTitle.trim() });
      } catch {}
    }
    setEditingId(null);
  };

  const startEdit = (e: React.MouseEvent, id: number, title: string) => {
    e.stopPropagation();
    setEditingId(id);
    setEditTitle(title);
  };

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: C.bg, borderRight: `1px solid ${C.border}`, overflow: "hidden" }}>
      <div style={{ padding: "10px 10px 6px", flexShrink: 0 }}>
        <button onClick={handleNew} style={{
          width: "100%", padding: "8px 0", background: C.cyanFaint, border: `1px solid ${C.border}`, borderRadius: 4,
          color: C.cyan, cursor: "pointer", fontSize: 13, fontFamily: "inherit", letterSpacing: "0.05em",
        }}>
          + Nuova chat
        </button>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "4px 6px" }}>
        {sessions.length === 0 && (
          <div style={{ color: C.textFaint, fontSize: 12, textAlign: "center", padding: 20 }}>Nessuna sessione</div>
        )}
        {sessions.map((s) => (
          <div key={s.id} onClick={() => handleSelect(s.id)} style={{
            display: "flex", alignItems: "center", gap: 4, padding: "7px 8px", marginBottom: 2, borderRadius: 4,
            cursor: "pointer", background: activeSessionId === s.id ? C.cyanFaint : "transparent",
            border: activeSessionId === s.id ? `1px solid ${C.border}` : "1px solid transparent",
            transition: "background 0.15s",
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              {editingId === s.id ? (
                <input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onBlur={() => handleRename(s.id)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleRename(s.id); if (e.key === "Escape") setEditingId(null); }}
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                  style={{ width: "100%", background: "rgba(0,0,0,0.3)", border: `1px solid ${C.cyan}`, color: C.text, fontSize: 12, padding: "2px 4px", outline: "none", borderRadius: 2, fontFamily: "inherit" }}
                />
              ) : (
                <div
                  onDoubleClick={(e) => startEdit(e, s.id, s.title)}
                  style={{ fontSize: 12, color: C.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                >
                  {s.title}
                </div>
              )}
              <div style={{ fontSize: 10, color: C.textFaint, marginTop: 1 }}>
                {s.message_count} msg · {new Date(s.created_at).toLocaleDateString()}
              </div>
            </div>
            <span
              onClick={(e) => handleDelete(e, s.id)}
              style={{ color: C.textFaint, cursor: "pointer", fontSize: 12, padding: "2px 4px", opacity: 0.5, flexShrink: 0 }}
              title="Elimina chat"
            >
              ✕
            </span>
          </div>
        ))}
      </div>
      {/* ── Voice Settings ── */}
      <div style={{flexShrink:0,borderTop:`1px solid ${C.border}`}}>
        <div onClick={()=>setVoiceOpen(!voiceOpen)} style={{padding:"8px 10px",cursor:"pointer",fontSize:12,color:C.cyan,fontFamily:"monospace",display:"flex",alignItems:"center",gap:6}}>
          <span style={{display:"inline-block",transform:voiceOpen?"rotate(90deg)":"none",transition:"transform 0.15s"}}>▶</span>
          🎤 Voce
          {vsDirty && <span onClick={e=>{e.stopPropagation();saveVs();}} style={{marginLeft:"auto",fontSize:10,color:C.green,cursor:"pointer"}}>Salva</span>}
        </div>
        {voiceOpen && (
          <div style={{padding:"0 10px 10px",fontSize:11,color:C.textDim}}>
            <label style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>
              <input type="checkbox" checked={!!vs.wake_word_enabled} onChange={e=>updateVs("wake_word_enabled",e.target.checked)} style={{accentColor:C.cyan}} />
              Wake word
            </label>
            <label style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>
              Sensibilità
              <input type="range" min="0.1" max="1.0" step="0.05" value={vs.wake_word_sensitivity??0.5} onChange={e=>updateVs("wake_word_sensitivity",parseFloat(e.target.value))} style={{flex:1,accentColor:C.cyan}} />
              <span style={{minWidth:28,fontFamily:"monospace",textAlign:"right"}}>{(vs.wake_word_sensitivity??0.5).toFixed(2)}</span>
            </label>
            <div style={{display:"flex",gap:4,marginBottom:4,alignItems:"center"}}>
              <span style={{flexShrink:0}}>STT</span>
              <select value={vs.stt_model??"base"} onChange={e=>updateVs("stt_model",e.target.value)} style={{flex:1,background:"#000",color:C.text,border:`1px solid ${C.border}`,borderRadius:2,fontSize:11,padding:"2px 4px"}}>
                {STT_MODELS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <select value={vs.stt_language??"auto"} onChange={e=>updateVs("stt_language",e.target.value)} style={{flex:1,background:"#000",color:C.text,border:`1px solid ${C.border}`,borderRadius:2,fontSize:11,padding:"2px 4px"}}>
                {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div style={{display:"flex",gap:4,marginBottom:4,alignItems:"center"}}>
              <span style={{flexShrink:0}}>TTS</span>
              <select value={vs.tts_engine??"kokoro"} onChange={e=>updateVs("tts_engine",e.target.value)} style={{flex:1,background:"#000",color:C.text,border:`1px solid ${C.border}`,borderRadius:2,fontSize:11,padding:"2px 4px"}}>
                {TTS_ENGINES.map(e => <option key={e} value={e}>{e}</option>)}
              </select>
              <label style={{display:"flex",alignItems:"center",gap:4}}>
                <input type="range" min="0.5" max="2.0" step="0.1" value={vs.tts_speed??1.0} onChange={e=>updateVs("tts_speed",parseFloat(e.target.value))} style={{width:50,accentColor:C.cyan}} />
                <span style={{minWidth:24,fontFamily:"monospace",textAlign:"right"}}>{(vs.tts_speed??1.0).toFixed(1)}x</span>
              </label>
            </div>
          </div>
        )}
      </div>
      {/* ── Batch Commands ── */}
      <div style={{flexShrink:0,borderTop:`1px solid ${C.border}`}}>
        <div onClick={()=>{}} style={{padding:"8px 10px",fontSize:12,color:C.cyan,fontFamily:"monospace",display:"flex",alignItems:"center",gap:6,cursor:"default"}}>
          ⚡ Batch
        </div>
        <div style={{padding:"0 10px 10px",fontSize:11,color:C.textDim}}>
          <textarea rows={3} placeholder="Comandi uno per riga&#10;es: ciao come stai?&#10;WAIT 2&#10;dimmi il meteo" style={{width:"100%",background:"rgba(0,0,0,0.3)",border:`1px solid ${C.border}`,borderRadius:2,color:C.text,fontSize:11,padding:"4px",resize:"vertical",fontFamily:"monospace"}} />
          <button onClick={async()=>{}} style={{marginTop:4,width:"100%",padding:"4px 0",background:C.cyanFaint,border:`1px solid ${C.border}`,borderRadius:2,color:C.cyan,cursor:"pointer",fontSize:11}}>Esegui batch</button>
        </div>
      </div>
    </div>
  );
}
