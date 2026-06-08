import { useEffect, useState } from "react";
import { useTheme } from "../theme";

const API_BASE = import.meta.env.VITE_API_BASE || "";

export default function HoldingsPanel({ gameId, playerId, refreshKey, onCardClick }) {
  const { theme } = useTheme();
  const [holdings, setHoldings] = useState(null);

  useEffect(() => {
    if (!gameId || !playerId) return;
    const token = sessionStorage.getItem(`squatter_session_token_${gameId}`);
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    fetch(`${API_BASE}/games/${gameId}/players/${playerId}/holdings`, { headers })
      .then((r) => (r.ok ? r.json() : null))
      .then(setHoldings)
      .catch(() => setHoldings(null));
  }, [gameId, playerId, refreshKey]);

  if (!holdings) return null;

  const isDark = theme.name === "dark";
  // Item-row backgrounds for the three section types. Darken slightly on
  // dark mode so they sit on the panel without bleaching the text.
  const paddockRowBg = isDark ? "#2a2a33" : "#fafafa";
  const cardRowBg = isDark ? "#3a2e4d" : "#f5f0e8";
  const cardRowBorder = isDark ? "#5a4673" : "#d4c5a3";
  const cardTitleColor = isDark ? "#c9b6e8" : "#6a4c93";
  const studRowBg = isDark ? "#1f3a2a" : "#e8f5e9";
  const studRowBorder = isDark ? "#3a6e4f" : "#a5d6a7";

  const { cards, stud_rams: studRams, states, paddocks = [] } = holdings;
  const typeColor = { natural: "#8d6e63", improved: "#66bb6a", irrigated: "#42a5f5" };
  const typeLabel = { natural: "Natural", improved: "Improved", irrigated: "Irrigated" };
  const totalPens = paddocks.reduce((s, p) => s + p.sheep_pens, 0);
  const totalCap = paddocks.reduce((s, p) => s + p.max_pens, 0);

  const stateBadges = [];
  if (states.has_haystack)
    stateBadges.push({ label: states.haystack_used ? "Haystack (used)" : "Haystack", color: "#a67c00" });
  if (states.footrot_immune)
    stateBadges.push({ label: "Footrot immune", color: "#388e3c" });
  if (states.is_in_drought)
    stateBadges.push({
      label: `Drought (${states.drought_spaces_remaining} spaces left)`,
      color: "#d32f2f",
    });
  if (states.restock_blocked_until_circuit)
    stateBadges.push({
      label: states.restock_block_spaces_remaining
        ? `Restock blocked (${states.restock_block_spaces_remaining} spaces left)`
        : "Restock blocked",
      color: "#d32f2f",
    });
  if (states.next_drought_halved)
    stateBadges.push({ label: "Next drought halved", color: "#1976d2" });
  if (states.next_sell_price_modifier)
    stateBadges.push({
      label: `+${states.next_sell_price_modifier}% next sell`,
      color: "#f57c00",
    });
  if (states.wool_cheque_bonus)
    stateBadges.push({
      label: `Wool bonus ${states.wool_cheque_bonus >= 0 ? "+" : ""}$${states.wool_cheque_bonus}`,
      color: states.wool_cheque_bonus >= 0 ? "#388e3c" : "#d32f2f",
    });
  if (states.visiting_town_turns > 0)
    stateBadges.push({
      label: `Visiting town: miss ${states.visiting_town_turns} turn(s)`,
      color: "#6a4c93",
    });

  return (
    <div
      style={{
        flex: "0 0 280px",
        position: "sticky",
        top: 20,
        background: theme.panelBg,
        color: theme.text,
        borderRadius: 8,
        border: `1px solid ${theme.panelBorder}`,
        padding: "12px",
        boxShadow: "0 2px 6px rgba(0,0,0,0.08)",
      }}
    >
      <h2 style={{ margin: "0 0 0.6rem", fontSize: "1.1rem" }}>Holdings</h2>

      {paddocks.length > 0 && (
        <section style={{ marginBottom: "0.8rem" }}>
          <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.9rem", color: theme.textMuted }}>
            Paddocks ({totalPens}/{totalCap} pens)
          </h3>
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {paddocks.map((p) => (
              <li key={p.paddock_number} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "4px 8px", marginBottom: 3, borderRadius: 4,
                background: paddockRowBg, color: theme.text,
                borderLeft: `4px solid ${typeColor[p.paddock_type]}`,
                opacity: p.is_mortgaged ? 0.55 : 1,
              }}>
                <span style={{ fontSize: "0.78rem" }}>
                  <strong>#{p.paddock_number}</strong>{" "}
                  <span style={{ color: typeColor[p.paddock_type] }}>{typeLabel[p.paddock_type]}</span>
                  {p.is_mortgaged && <span style={{ marginLeft: 4, color: "#ef5350", fontSize: "0.7rem" }}>(mortgaged)</span>}
                </span>
                <span style={{ fontSize: "0.78rem", fontFamily: "monospace" }}>
                  {p.sheep_pens}/{p.max_pens}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section style={{ marginBottom: "0.8rem" }}>
        <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.9rem", color: theme.textMuted }}>
          Cards ({cards.length})
        </h3>
        {cards.length === 0 ? (
          <p style={{ margin: 0, fontSize: "0.8rem", color: theme.textSubtle }}>None</p>
        ) : (
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {cards.map((c) => (
              <li
                key={c.card_draw_id}
                onClick={() => onCardClick?.(c)}
                style={{
                  marginBottom: 6,
                  padding: "8px 10px",
                  borderRadius: 6,
                  background: cardRowBg,
                  border: `1px solid ${cardRowBorder}`,
                  cursor: onCardClick ? "pointer" : "default",
                }}
              >
                <div style={{ fontWeight: "bold", fontSize: "0.85rem", color: cardTitleColor }}>
                  {c.title}
                </div>
                <div style={{ fontSize: "0.7rem", color: theme.textMuted, marginTop: 2 }}>
                  {c.deck_type === "tucker_bag" ? "Tucker Bag" : "Expense Immunity"}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={{ marginBottom: "0.8rem" }}>
        <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.9rem", color: theme.textMuted }}>
          Stud Rams ({studRams.length})
        </h3>
        {studRams.length === 0 ? (
          <p style={{ margin: 0, fontSize: "0.8rem", color: theme.textSubtle }}>None</p>
        ) : (
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {studRams.map((r) => (
              <li
                key={r.space_id}
                style={{
                  marginBottom: 6,
                  padding: "8px 10px",
                  borderRadius: 6,
                  background: studRowBg,
                  color: theme.text,
                  border: `1px solid ${studRowBorder}`,
                }}
              >
                <div style={{ fontWeight: "bold", fontSize: "0.85rem" }}>{r.space_name}</div>
                <div style={{ fontSize: "0.7rem", color: theme.textMuted }}>
                  Stud fee: ${r.stud_fee}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {stateBadges.length > 0 && (
        <section>
          <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.9rem", color: theme.textMuted }}>
            Status
          </h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {stateBadges.map((b, i) => (
              <span
                key={i}
                style={{
                  fontSize: "0.7rem",
                  padding: "2px 6px",
                  borderRadius: 4,
                  background: b.color,
                  color: "#fff",
                }}
              >
                {b.label}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
