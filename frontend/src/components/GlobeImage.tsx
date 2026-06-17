import { C } from "../utils/theme";

export function GlobeImage() {
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
