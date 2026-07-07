import type { ReactNode } from "react";
import { _md } from "../utils/markdown";

export function MarkdownRenderer({ content }: { content: string }) {
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
