const API_BASE = import.meta.env.VITE_API_BASE || '';

/* Red debt notice for the local player. Balances go negative when forced
   payments exceed cash; the server gates the whole game until the debt is
   cleared, so surface the obligation the moment it exists. Shown only once
   this turn's other modals (expense OK, etc.) are acknowledged, so the
   order is: acknowledge -> settle -> play. */
export default function DebtBanner({
  gameId, sessionToken, currentUserPlayer, playerBalances, stations,
  pendingAction, onOpenStation, onRefresh, onError,
}) {
  if (!currentUserPlayer || currentUserPlayer.is_active === false) return null;

  const balance = playerBalances[String(currentUserPlayer.game_player_id)];
  const debt = (typeof balance === 'number' && balance < 0) ? -balance : 0;
  if (debt <= 0) return null;
  if (pendingAction && pendingAction.action_type !== 'debt_settlement') return null;

  const station = stations[String(currentUserPlayer.game_player_id)]
    || stations[currentUserPlayer.game_player_id];
  // Pens to sell at the $400 emergency price to exactly clear the debt.
  const pensNeeded = Math.min(Math.ceil(debt / 400), station?.total_pens ?? 0);

  const emergencySell = async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/station/sell-to-bank`, {
        method: "POST",
        headers: { 'Authorization': `Bearer ${sessionToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ pens: pensNeeded })
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed: ${response.status}`);
      }
      onRefresh();
    } catch (err) {
      onError(err.message);
    }
  };

  return (
    <div style={{
      background: "#b71c1c", color: "#fff", padding: "0.75rem 1rem",
      borderRadius: 8, marginBottom: "1rem", fontSize: "0.95rem",
      boxShadow: "0 2px 8px rgba(0,0,0,0.3)"
    }}>
      <strong>⚠ You are ${debt} in debt.</strong>
      <div style={{ marginTop: 4 }}>
        You must raise cash before play continues — sell sheep to the
        bank at $400/pen, mortgage paddocks, or sell a stud ram /
        haystack. If your assets cannot cover the debt, your station
        will be declared bankrupt.
      </div>
      <div style={{ display: "flex", gap: "0.5rem", marginTop: 8, flexWrap: "wrap" }}>
        {pensNeeded > 0 && (
          <button onClick={emergencySell} style={{
            padding: "0.4rem 1rem", background: "#fff",
            color: "#b71c1c", border: "none", borderRadius: 6,
            cursor: "pointer", fontWeight: "bold", fontSize: "0.9rem"
          }}>
            Emergency Sell {pensNeeded} pen{pensNeeded > 1 ? 's' : ''} (+${pensNeeded * 400})
          </button>
        )}
        <button onClick={onOpenStation} style={{
          padding: "0.4rem 1rem", background: "rgba(255,255,255,0.25)",
          color: "#fff", border: "1px solid rgba(255,255,255,0.6)",
          borderRadius: 6, cursor: "pointer", fontSize: "0.9rem"
        }}>Station Panel</button>
      </div>
    </div>
  );
}
