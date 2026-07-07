import type { ReactNode } from "react";
import { C, mono } from "../utils/theme";

export function Panel({ children, style, title, accent = C.cyan }: {
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
