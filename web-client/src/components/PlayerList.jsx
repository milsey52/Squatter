import { useTheme } from "../theme";

const SPACE_LABELS = [
  "Start/Wool Sale", "Stock Sale", "Sheep Dipping", "Stud Ram – Elmsford",
  "Tucker Bag", "Bore Dries Up", "Visiting Town", "Visiting Town",
  "Drench Sheep for Worms", "Tucker Bag", "Flood Damage", "Tucker Bag",
  "Stock Sale", "Shearing Costs", "Control of Vermin", "Stock Sale",
  "Footrot Treatment", "Stock Sale", "Stud Ram – Lachlan Lad", "Tucker Bag",
  "Fencing Repairs", "Spray for Weeds & Insects", "Local Drought", "Liver Fluke Drench",
  "Tucker Bag", "Stock Sale", "Stud Ram – King of Warramboo", "Local Rain",
  "Stock Sale", "Pulpy Kidney Vaccine", "Stud Ram – Winton Boy", "Tucker Bag",
  "Stock Sale", "Stud Ram Dies", "Water Drilling", "Tucker Bag",
  "Stock Sale", "Fertilising Pasture", "Stock Sale", "Stud Ram – Mitchell's Pride",
  "Fly Strike Dip", "Tucker Bag", "Stock Sale", "Local Drought"
];

/* The Players sidebar: one row per player with position, cash, pens,
   status chips and retained cards. Click a row to view that station. */
export default function PlayerList({
  players, currentPlayerId, playerBalances, stations, playerRetainedCards,
  onViewPlayer, onCardClick,
}) {
  const { theme } = useTheme();
  return (
    <>
      <h2 style={{ margin: "0 0 0.5rem" }}>Players</h2>
      <ul style={{ paddingLeft: "1rem", listStyle: "none" }}>
        {players.map((p) => {
          const spaceLabel = SPACE_LABELS[p.current_board_index] || `Space ${p.current_board_index}`;
          const cash = playerBalances[String(p.game_player_id)] ?? "?";
          const station = stations[String(p.game_player_id)] || stations[p.game_player_id];
          const totalPens = station?.total_pens ?? "?";
          const retained = playerRetainedCards[p.game_player_id] || [];
          const isCurrent = p.game_player_id === currentPlayerId;

          return (
            <li key={p.game_player_id} style={{
              marginBottom: 10, padding: "10px", borderRadius: "8px",
              background: isCurrent ? theme.highlightBg : "transparent",
              color: isCurrent && theme.name === "dark" ? theme.text : undefined,
              border: isCurrent ? `2px solid ${theme.highlightBorder}` : `1px solid ${theme.panelBorder}`,
              opacity: p.is_active === false ? 0.5 : 1
            }}>
              <div
                onClick={() => onViewPlayer(p.game_player_id)}
                title="Click to view this player's station"
                style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap", cursor: "pointer" }}
              >
                <strong style={{ textDecoration: "underline dotted", textUnderlineOffset: 3 }}>{p.player_name}</strong>
                {p.is_active === false && (
                  <span style={{
                    padding: "1px 6px", borderRadius: 4, background: "#424242",
                    color: "#fff", fontSize: "0.7rem", fontWeight: "bold",
                  }}>BANKRUPT</span>
                )}
                {p.is_ai && (
                  <span style={{
                    padding: "1px 6px", borderRadius: 4, background: "#6a4c93",
                    color: "#fff", fontSize: "0.7rem", fontWeight: "bold",
                  }}>🤖 AI{p.ai_difficulty ? ` · ${p.ai_difficulty.toUpperCase()}` : ''}</span>
                )}
                <span style={{ fontSize: "0.85rem", color: theme.textMuted }}>{spaceLabel}</span>
                <span style={{ fontSize: "0.85rem", color: "#1982c4" }}>${cash}</span>
                <span style={{ fontSize: "0.85rem", color: "#4caf50" }}>{totalPens} pens</span>
                {p.is_in_drought && <span style={{ fontSize: "0.8rem", color: "#d32f2f" }}>DROUGHT</span>}
                {p.visiting_town_turns > 0 && <span style={{ fontSize: "0.8rem", color: "#ff9800" }}>Town ({p.visiting_town_turns})</span>}
                {p.haystack_pasture && <span style={{ fontSize: "0.8rem", color: "#795548" }}>Hay-P</span>}
                {p.haystack_irrigated && <span style={{ fontSize: "0.8rem", color: "#0277bd" }}>Hay-I</span>}
              </div>
              {retained.length > 0 && (
                <div style={{ fontSize: "0.8rem", color: "#6a4c93", marginTop: "4px" }}>
                  Cards: {retained.map((card, i) => (
                    <button key={i} onClick={(e) => { e.stopPropagation(); onCardClick(card); }} style={{
                      background: 'none', border: 'none', color: '#6a4c93',
                      textDecoration: 'underline', cursor: 'pointer', padding: 0, font: 'inherit'
                    }}>{card.title}{i < retained.length - 1 ? ", " : ""}</button>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}
