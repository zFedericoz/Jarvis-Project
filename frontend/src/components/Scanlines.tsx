export function Scanlines({ theme }: { theme?: "dark" | "light" }) {
  if (theme === "light") return null;
  return (
    <div style={{
      pointerEvents: "none", position: "absolute", inset: 0, zIndex: 9999,
      background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.07) 2px, rgba(0,0,0,0.07) 4px)",
    }} />
  );
}
