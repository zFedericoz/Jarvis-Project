export type ThemeName = "dark" | "light";

export interface Theme {
  bg: string; bgPanel: string; bgPanelHover: string;
  cyan: string; cyanDim: string; cyanFaint: string;
  green: string; greenDim: string; amber: string;
  red: string; purple: string;
  border: string; borderStrong: string;
  text: string; textDim: string; textFaint: string;
}

export const THEMES: Record<ThemeName, Theme> = {
  dark: {
    bg: "#050e14", bgPanel: "#071520", bgPanelHover: "#0a1e2e",
    cyan: "#00e5ff", cyanDim: "#00b8cc", cyanFaint: "rgba(0,229,255,0.08)",
    green: "#00ff88", greenDim: "#00cc6a", amber: "#ffaa00",
    red: "#ff4455", purple: "#a855f7",
    border: "rgba(0,229,255,0.18)", borderStrong: "rgba(0,229,255,0.45)",
    text: "#c8eef8", textDim: "rgba(200,238,248,0.6)", textFaint: "rgba(200,238,248,0.3)",
  },
  light: {
    bg: "#f8fafc", bgPanel: "#f1f5f9", bgPanelHover: "#e2e8f0",
    cyan: "#0369a1", cyanDim: "#0284c7", cyanFaint: "#e0f2fe",
    green: "#059669", greenDim: "#047857", amber: "#d97706",
    red: "#dc2626", purple: "#7c3aed",
    border: "#cbd5e1", borderStrong: "#94a3b8",
    text: "#0f172a", textDim: "#475569", textFaint: "#94a3b8",
  },
};

let _current: Theme = THEMES.dark;

export function setTheme(t: ThemeName) {
  _current = THEMES[t];
}

export const C = new Proxy<Theme>({} as Theme, {
  get(_, prop) {
    return _current[prop as keyof Theme];
  },
});

export const font = "'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif";
export const mono = "'JetBrains Mono', 'Consolas', 'Courier New', monospace";
