import { useState, useEffect } from "react";
import { useTheme } from "../theme";

const API_BASE = import.meta.env.VITE_API_BASE || "";

/**
 * Settings modal. Sections are designed to grow as new settings come in.
 * Sections currently present:
 *   - Theme (light / dark) — per-browser via localStorage.
 *   - AI reaction time (1-10s) — per-game; host-only.
 */
export default function SettingsModal({
  gameId, sessionToken, isHost = false,
  aiReactionTimeSeconds = 4,
  onClose,
  onSettingsChanged,
}) {
  const { theme, mode, setMode } = useTheme();
  const [aiSeconds, setAiSeconds] = useState(aiReactionTimeSeconds);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState(null);

  useEffect(() => {
    setAiSeconds(aiReactionTimeSeconds);
  }, [aiReactionTimeSeconds]);

  const saveAiSeconds = async () => {
    if (!gameId || !sessionToken || !isHost) return;
    setAiBusy(true);
    setAiError(null);
    try {
      const res = await fetch(`${API_BASE}/games/${gameId}/settings/ai-reaction-time`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${sessionToken}`, "Content-Type": "application/json" },
        body: JSON.stringify({ seconds: aiSeconds }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || `Failed: ${res.status}`);
      onSettingsChanged?.();
    } catch (e) {
      setAiError(e.message);
    } finally {
      setAiBusy(false);
    }
  };

  const overlay = {
    position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
    background: "rgba(0,0,0,0.5)", display: "flex",
    alignItems: "center", justifyContent: "center", zIndex: 9500,
  };
  const card = {
    background: theme.modalBg, color: theme.modalText,
    borderRadius: 12, padding: "1.5rem 1.75rem",
    minWidth: 380, maxWidth: 500, width: "90%",
    boxShadow: `0 10px 40px ${theme.modalShadow}`,
    position: "relative",
  };
  const closeBtn = {
    position: "absolute", top: 10, right: 12,
    background: "transparent", border: "none",
    fontSize: "1.4rem", cursor: "pointer", color: theme.textMuted,
  };
  const sectionStyle = {
    padding: "0.75rem 0",
    borderTop: `1px solid ${theme.divider}`,
  };
  const labelStyle = {
    fontSize: "0.85rem", color: theme.textMuted, marginBottom: 6,
    fontWeight: "bold", textTransform: "uppercase", letterSpacing: 1,
  };
  const radioRow = {
    display: "flex", gap: "0.5rem", marginTop: "0.5rem",
  };
  const radioBtn = (active, color) => ({
    flex: 1, padding: "0.6rem 0.8rem",
    background: active ? color : "transparent",
    color: active ? "#fff" : theme.text,
    border: `2px solid ${color}`,
    borderRadius: 6, cursor: "pointer", fontWeight: "bold",
    fontSize: "0.9rem",
  });

  return (
    <div style={overlay} onClick={onClose}>
      <div style={card} onClick={(e) => e.stopPropagation()}>
        <button style={closeBtn} onClick={onClose} aria-label="Close">×</button>
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.2rem" }}>Settings</h2>

        {/* Theme */}
        <div style={{ ...sectionStyle, borderTop: "none", paddingTop: 0 }}>
          <div style={labelStyle}>Theme</div>
          <div style={radioRow}>
            <button style={radioBtn(mode === "light", "#1982c4")}
              onClick={() => setMode("light")}>☾ Light</button>
            <button style={radioBtn(mode === "dark", "#6a4c93")}
              onClick={() => setMode("dark")}>☀ Dark</button>
          </div>
        </div>

        {/* AI reaction time */}
        <div style={sectionStyle}>
          <div style={labelStyle}>AI reaction time</div>
          <p style={{ fontSize: "0.82rem", color: theme.textMuted, margin: "0 0 0.5rem" }}>
            How long an AI-owned modal stays visible before the AI dismisses it.
            {!isHost && " Only the host can change this."}
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <input type="range" min={1} max={10} step={1}
              value={aiSeconds}
              disabled={!isHost || aiBusy}
              onChange={(e) => setAiSeconds(Number(e.target.value))}
              style={{ flex: 1 }} />
            <span style={{ minWidth: 60, fontWeight: "bold", color: theme.text }}>
              {aiSeconds}s
            </span>
          </div>
          {isHost && (
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
              <button
                onClick={saveAiSeconds}
                disabled={aiBusy || aiSeconds === aiReactionTimeSeconds}
                style={{
                  padding: "0.45rem 0.9rem", background: aiSeconds === aiReactionTimeSeconds ? "#888" : "#4caf50",
                  color: "#fff", border: "none", borderRadius: 6,
                  cursor: (aiBusy || aiSeconds === aiReactionTimeSeconds) ? "not-allowed" : "pointer",
                  fontSize: "0.85rem", fontWeight: "bold",
                }}>
                {aiBusy ? "Saving..." : aiSeconds === aiReactionTimeSeconds ? "Saved" : "Save"}
              </button>
              {aiError && <span style={{ color: "#e57373", fontSize: "0.82rem", alignSelf: "center" }}>{aiError}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


/** Convenience gear button — opens the modal when clicked. */
export function SettingsButton({ onClick, style = {} }) {
  const { mode } = useTheme();
  const isDark = mode === "dark";
  return (
    <button
      onClick={onClick}
      title="Settings"
      aria-label="Settings"
      style={{
        padding: "0.5rem 0.85rem",
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
      <span style={{ fontSize: "1.1rem" }}>⚙</span>
      <span>Settings</span>
    </button>
  );
}
