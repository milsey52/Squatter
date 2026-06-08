// Theme tokens + context + toggle.
// Lite dark theme: page background, panels, modals, text. Semantic accent
// colours (red/green/orange) and the board.svg are not themed in v1.
import { createContext, useContext, useEffect, useState, useCallback } from "react";

export const LIGHT = {
  name: "light",
  pageBg: "#ffffff",
  cardBg: "#ffffff",
  panelBg: "#ffffff",
  panelBorder: "#e0e0e0",
  panelBorderStrong: "#999999",
  text: "#333333",
  textMuted: "#666666",
  textSubtle: "#888888",
  inputBg: "#ffffff",
  inputBorder: "#cccccc",
  highlightBg: "linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)",
  highlightBorder: "#4caf50",
  modalBg: "#ffffff",
  modalText: "#333333",
  modalShadow: "rgba(0,0,0,0.3)",
  rowAltBg: "#fafafa",
  divider: "#cccccc",
};

export const DARK = {
  name: "dark",
  pageBg: "#1a1a1f",
  cardBg: "#23232b",
  panelBg: "#23232b",
  panelBorder: "#3a3a45",
  panelBorderStrong: "#555560",
  text: "#e6e6ea",
  textMuted: "#a8a8b0",
  textSubtle: "#787880",
  inputBg: "#2c2c35",
  inputBorder: "#44444f",
  highlightBg: "linear-gradient(135deg, #1f3a2a 0%, #2a4c38 100%)",
  highlightBorder: "#4caf50",
  modalBg: "#23232b",
  modalText: "#e6e6ea",
  modalShadow: "rgba(0,0,0,0.7)",
  rowAltBg: "#2a2a33",
  divider: "#3a3a45",
};

const ThemeContext = createContext({ theme: LIGHT, setMode: () => {}, mode: "light" });

const STORAGE_KEY = "squatter_theme";

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved === "dark" ? "dark" : "light";
    } catch {
      return "light";
    }
  });

  const setMode = useCallback((newMode) => {
    const m = newMode === "dark" ? "dark" : "light";
    try { localStorage.setItem(STORAGE_KEY, m); } catch { /* ignore */ }
    setModeState(m);
  }, []);

  const theme = mode === "dark" ? DARK : LIGHT;

  // Reflect onto <body> so the whole page picks up the bg even before any
  // React component renders.
  useEffect(() => {
    document.body.style.background = theme.pageBg;
    document.body.style.color = theme.text;
    document.documentElement.style.colorScheme = mode;
  }, [theme, mode]);

  return (
    <ThemeContext.Provider value={{ theme, mode, setMode }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

// Small reusable toggle button. Drop it anywhere — top of lobby, next to
// Logout, etc.
export function ThemeToggle({ style = {} }) {
  const { mode, setMode } = useTheme();
  const isDark = mode === "dark";
  const labelText = isDark ? "Light theme" : "Dark theme";
  return (
    <button
      onClick={() => setMode(isDark ? "light" : "dark")}
      title={isDark ? "Switch to light theme" : "Switch to dark theme"}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      style={{
        padding: "0.5rem 0.9rem",
        background: isDark ? "#3a3a45" : "#1982c4",
        color: isDark ? "#ffd54f" : "#ffffff",
        border: `2px solid ${isDark ? "#ffd54f" : "#1565a0"}`,
        borderRadius: 6,
        cursor: "pointer",
        fontSize: "0.95rem",
        fontWeight: "bold",
        lineHeight: 1,
        display: "inline-flex",
        alignItems: "center",
        gap: "0.4rem",
        boxShadow: "0 2px 4px rgba(0,0,0,0.15)",
        ...style,
      }}
    >
      <span style={{ fontSize: "1.1rem" }}>{isDark ? "☀" : "☾"}</span>
      <span>{labelText}</span>
    </button>
  );
}
