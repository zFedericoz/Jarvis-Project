import { C, mono } from "../utils/theme";
import { MiniChart } from "./MiniChart";

export function MetricBadge({ label, value, unit, color, history }: { label: string; value: string | number; unit: string; color: string; history?: number[] }) {
  return (
    <div style={{display:"flex",alignItems:"center",gap:6,fontFamily:mono,fontSize:12,color:C.text,borderRight:`1px solid ${C.border}`,paddingRight:10}}>
      <span style={{color:C.textFaint,fontSize:10,letterSpacing:"0.05em"}}>{label}</span>
      <span style={{color,fontWeight:"bold",fontSize:14}}>{value}<span style={{fontSize:10,color:C.textDim,marginLeft:1}}>{unit}</span></span>
      {history && <MiniChart data={history} color={color} />}
    </div>
  );
}
