import { useEffect, useState } from "react";
import { useStore } from "../hooks/useStore";
import { API_URL } from "../utils/constants";

const C = {
  bg: "#071520",
  border: "rgba(0,229,255,0.18)",
  cyan: "#00e5ff",
  cyanFaint: "rgba(0,229,255,0.08)",
  textDim: "rgba(200,238,248,0.6)",
  textFaint: "rgba(200,238,248,0.3)",
  text: "#c8eef8",
  green: "#00ff88",
};

export default function Sidebar() {
  const { sessions, activeSessionId, setActiveSessionId, setSessions, addSession, removeSession, updateSession, setChatHistory } = useStore();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/chats`)
      .then((r) => r.json())
      .then((d) => { if (d.sessions) setSessions(d.sessions); })
      .catch(() => {});
  }, []);

  const handleNew = async () => {
    try {
      const r = await fetch(`${API_URL}/chats`, { method: "POST" });
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
      const r = await fetch(`${API_URL}/chats/${id}/messages`);
      const d = await r.json();
      if (d.messages) setChatHistory(d.messages);
    } catch {}
  };

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      await fetch(`${API_URL}/chats/${id}`, { method: "DELETE" });
      removeSession(id);
      if (activeSessionId === id) setChatHistory([]);
    } catch {}
  };

  const handleRename = async (id: number) => {
    if (editTitle.trim()) {
      try {
        await fetch(`${API_URL}/chats/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: editTitle.trim() }) });
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
    </div>
  );
}
