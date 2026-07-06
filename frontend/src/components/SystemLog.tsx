import { useState, useEffect, useRef } from "react";
import { C, mono } from "../utils/theme";
import { fetchFromBest, fetchWithAuth } from "../utils/fetch";

const HOST_METRICS_URL = "http://localhost:18765";
const DOCKER_API = "";

function Skeleton({ rows }: { rows: number }) {
  return (
    <div style={{ fontFamily: mono, fontSize: 11, lineHeight: 1.6, paddingRight: 4 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{
          height: 13, marginBottom: 4, borderRadius: 2,
          background: `linear-gradient(90deg, ${C.border} 0%, ${C.bgPanel} 50%, ${C.border} 100%)`,
          backgroundSize: "200% 100%",
          animation: "shimmer 1.5s ease-in-out infinite",
          width: `${40 + Math.random() * 50}%`,
          opacity: 0.5,
        }} />
      ))}
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
    </div>
  );
}

export function SystemLog({ compact }: { compact?: boolean }) {
  const [logs, setLogs] = useState<{timestamp:string;level:string;message:string}[]>([]);
  const [loading, setLoading] = useState(true);
  const endRef = useRef<HTMLDivElement>(null!);
  useEffect(() => {
    const fetchLogs = async () => {
      let d = await fetchFromBest([`${HOST_METRICS_URL}/api/system/logs`], 2000);
      if (!d) {
        try { const r = await fetchWithAuth(`${DOCKER_API}/api/system/logs`); if (r.ok) d = await r.json(); } catch {}
      }
      if (d?.logs) setLogs(d.logs.slice(-20));
      setLoading(false);
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
  if (loading) return <Skeleton rows={8} />;
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
