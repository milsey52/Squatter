import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || '';

const money = (n) => `${n < 0 ? '-$' : '$'}${Math.abs(n ?? 0).toLocaleString()}`;

/* End-of-game celebratory banner + final standings table (every player's
   financial position, richest first). Shown on the game_over SSE event or a
   game_won pending action. Acknowledges the lingering pending on exit so
   future joiners don't re-trigger it. */
export default function WinnerBanner({
  gameId, sessionToken, pendingAction, winner, gameOver, zIndex, onReturnToMenu,
}) {
  const gameWonPending = pendingAction?.action_type === 'game_won' ? pendingAction : null;
  const winnerName = winner || gameWonPending?.action_data?.winner_name;
  const show = (gameOver || !!gameWonPending) && !!winnerName;
  const reason = gameWonPending?.action_data?.reason;

  const [standings, setStandings] = useState(null);

  useEffect(() => {
    if (!show || !gameId) return;
    fetch(`${API_BASE}/games/${gameId}/standings`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setStandings(d?.standings || null))
      .catch(() => setStandings(null));
  }, [show, gameId]);

  if (!show) return null;

  const returnToMenu = async () => {
    if (gameWonPending) {
      try {
        await fetch(`${API_BASE}/games/${gameId}/decisions/acknowledge`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${sessionToken}` },
        });
      } catch { /* ignore */ }
    }
    onReturnToMenu();
  };

  return (
    <div style={{
      position: "absolute", top: "50%", left: 0, right: 0,
      transform: "translateY(-50%)", zIndex,
      background: "linear-gradient(135deg, #ff6f00 0%, #ffb300 50%, #ff6f00 100%)",
      border: "6px double #fff", boxShadow: "0 8px 32px rgba(0,0,0,0.45)",
      padding: "1.4rem 1rem", textAlign: "center",
    }}>
      <div style={{
        fontSize: "2.4rem", fontWeight: 900, color: "#fff",
        textShadow: "2px 3px 8px rgba(0,0,0,0.5)", letterSpacing: 2,
        fontFamily: "'Georgia', serif",
      }}>
        {winnerName} is WINNER!!!!
      </div>
      <div style={{ fontSize: "0.95rem", color: "#fff8e1", marginTop: 6, fontStyle: "italic" }}>
        {reason === 'last_player_standing'
          ? 'Last station standing — everyone else went bankrupt'
          : '6,000 sheep on a fully irrigated farm'}
      </div>

      {standings && standings.length > 0 && (
        <div style={{
          margin: "1rem auto 0", maxWidth: 720, background: "rgba(255,255,255,0.95)",
          borderRadius: 8, padding: "0.6rem 0.8rem", color: "#333",
        }}>
          <div style={{ fontWeight: "bold", fontSize: "0.85rem", marginBottom: 4, color: "#555" }}>
            Final Standings
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #ccc", color: "#666" }}>
                <th style={{ textAlign: "left", padding: "3px 6px" }}>#</th>
                <th style={{ textAlign: "left", padding: "3px 6px" }}>Player</th>
                <th style={{ textAlign: "right", padding: "3px 6px" }}>Cash</th>
                <th style={{ textAlign: "right", padding: "3px 6px" }}>Sheep</th>
                <th style={{ textAlign: "right", padding: "3px 6px" }}>Paddocks</th>
                <th style={{ textAlign: "center", padding: "3px 6px" }}>Hay</th>
                <th style={{ textAlign: "right", padding: "3px 6px" }}>Rams</th>
                <th style={{ textAlign: "right", padding: "3px 6px" }}>Net Worth</th>
              </tr>
            </thead>
            <tbody>
              {standings.map((s, i) => {
                const isWinner = s.player_name === winnerName;
                return (
                  <tr key={s.game_player_id} style={{
                    borderBottom: "1px solid #eee",
                    background: isWinner ? "#fff3c4" : "transparent",
                    opacity: s.is_active ? 1 : 0.6,
                  }}>
                    <td style={{ padding: "3px 6px" }}>{i + 1}</td>
                    <td style={{ padding: "3px 6px", textAlign: "left", fontWeight: isWinner ? "bold" : "normal" }}>
                      {isWinner && "👑 "}{s.player_name}
                      {s.is_ai && <span style={{ color: "#6a4c93", fontSize: "0.72rem" }}> AI</span>}
                      {!s.is_active && <span style={{ color: "#b71c1c", fontSize: "0.72rem", fontWeight: "bold" }}> BANKRUPT</span>}
                    </td>
                    <td style={{ padding: "3px 6px", textAlign: "right", fontFamily: "monospace", color: s.cash < 0 ? "#b71c1c" : "#333" }}>
                      {money(s.cash)}
                    </td>
                    <td style={{ padding: "3px 6px", textAlign: "right", fontFamily: "monospace" }}>{s.sheep_pens}p</td>
                    <td style={{ padding: "3px 6px", textAlign: "right", fontFamily: "monospace" }}>
                      {s.paddocks_owned}{s.paddocks_mortgaged ? ` (${s.paddocks_mortgaged}m)` : ""}
                    </td>
                    <td style={{ padding: "3px 6px", textAlign: "center" }}>{s.has_haystack ? "✓" : ""}</td>
                    <td style={{ padding: "3px 6px", textAlign: "right", fontFamily: "monospace" }}>{s.stud_rams || ""}</td>
                    <td style={{ padding: "3px 6px", textAlign: "right", fontFamily: "monospace", fontWeight: "bold", color: s.net_worth < 0 ? "#b71c1c" : "#1b5e20" }}>
                      {money(s.net_worth)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <button onClick={returnToMenu} style={{
        marginTop: 12, padding: "0.6rem 1.4rem", background: "#fff",
        color: "#ff6f00", border: "none", borderRadius: 8,
        fontSize: "1rem", fontWeight: "bold", cursor: "pointer",
      }}>
        Return to Menu
      </button>
    </div>
  );
}
