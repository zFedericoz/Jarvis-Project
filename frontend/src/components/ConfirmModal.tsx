import { C, mono } from "../utils/theme";

export function ConfirmModal({ pendingActionLabel, confirming, onConfirm }: {
  pendingActionLabel: string;
  confirming: boolean;
  onConfirm: (confirm: boolean) => void;
}) {
  return (
    <div style={{position:"absolute",inset:0,background:"rgba(0,0,0,0.6)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:10000}}>
      <div style={{background:C.bgPanel,border:`1px solid ${C.amber}`,borderRadius:6,padding:"20px 24px",maxWidth:400,width:"90%",textAlign:"center"}}>
        <div style={{fontSize:32,marginBottom:8}}>⚠️</div>
        <div style={{fontFamily:mono,fontSize:12,color:C.amber,letterSpacing:"0.1em",marginBottom:4,textTransform:"uppercase"}}>Conferma azione</div>
        <div style={{fontSize:14,color:C.text,marginBottom:16}}>
          J.A.R.V.I.S. vuole eseguire <strong style={{color:C.amber}}>{pendingActionLabel}</strong>.
          <br/>Procedere?
        </div>
        <div style={{display:"flex",gap:10,justifyContent:"center"}}>
          <button onClick={()=>onConfirm(false)} disabled={confirming}
            style={{background:"transparent",border:`1px solid ${C.border}`,color:C.textDim,borderRadius:4,padding:"6px 18px",cursor:"pointer",fontFamily:mono,fontSize:12}}>
            Annulla
          </button>
          <button onClick={()=>onConfirm(true)} disabled={confirming}
            style={{background:C.amber,border:"none",color:"#000",borderRadius:4,padding:"6px 18px",cursor:"pointer",fontFamily:mono,fontSize:12,fontWeight:"bold"}}>
            {confirming ? "...esecuzione" : "Conferma"}
          </button>
        </div>
      </div>
    </div>
  );
}
