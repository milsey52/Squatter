import { useEffect, useState } from "react";
import { Z_INDEX } from "../constants/zIndex";
import { useTheme } from "../theme";

const API_BASE = import.meta.env.VITE_API_BASE || "";

const TYPE_COLOR = { natural: "#8d6e63", improved: "#66bb6a", irrigated: "#42a5f5" };
const TYPE_LABEL = { natural: "Natural", improved: "Improved", irrigated: "Irrigated" };

export default function PlayerStationModal({ gameId, playerId, playerName, onClose, onCardClick }) {
  const { theme } = useTheme();
  const [holdings, setHoldings] = useState(null);

  useEffect(() => {
    if (!gameId || !playerId) return;
    fetch(`${API_BASE}/games/${gameId}/players/${playerId}/holdings`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setHoldings)
      .catch(() => setHoldings(null));
  }, [gameId, playerId]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const overlayStyle = {
    position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
    background: "rgba(0,0,0,0.45)", display: "flex",
    alignItems: "center", justifyContent: "center", zIndex: Z_INDEX.MODAL,
  };
  const modalStyle = {
    background: theme.modalBg, color: theme.modalText, borderRadius: 10, padding: "18px 22px",
    minWidth: 380, maxWidth: 520, maxHeight: "85vh", overflowY: "auto",
    boxShadow: `0 8px 32px ${theme.modalShadow}`, position: "relative",
  };
  const closeBtn = {
    position: "absolute", top: 10, right: 12, background: "transparent",
    border: "none", fontSize: "1.2rem", cursor: "pointer", color: "#666",
  };

  const renderBody = () => {
    if (!holdings) return <p style={{ margin: 0 }}>Loading...</p>;

    const { cards = [], stud_rams: studRams = [], states = {}, paddocks = [], financials } = holdings;
    const totalPens = paddocks.reduce((s, p) => s + p.sheep_pens, 0);
    const totalCap = paddocks.reduce((s, p) => s + p.max_pens, 0);

    const fin = financials || {};
    const money = (n) => `${n < 0 ? "-$" : "$"}${Math.abs(n ?? 0).toLocaleString()}`;
    const finRow = (label, value, opts = {}) => (
      <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", fontSize: "0.85rem" }}>
        <span style={{ color: "#555" }}>{label}</span>
        <span style={{ fontFamily: "monospace", fontWeight: opts.bold ? "bold" : "normal", color: opts.color }}>{value}</span>
      </div>
    );

    const stateBadges = [];
    if (states.has_haystack) stateBadges.push({ label: states.haystack_used ? "Haystack (used)" : "Haystack", color: "#a67c00" });
    if (states.footrot_immune) stateBadges.push({ label: "Footrot immune", color: "#388e3c" });
    if (states.is_in_drought) stateBadges.push({ label: `Drought (${states.drought_spaces_remaining} spaces left)`, color: "#d32f2f" });
    if (states.restock_blocked_until_circuit) stateBadges.push({
      label: states.restock_block_spaces_remaining
        ? `Restock blocked (${states.restock_block_spaces_remaining} spaces left)`
        : "Restock blocked",
      color: "#d32f2f",
    });
    if (states.next_drought_halved) stateBadges.push({ label: "Next drought halved", color: "#1976d2" });
    if (states.next_sell_price_modifier) stateBadges.push({ label: `+${states.next_sell_price_modifier}% next sell`, color: "#f57c00" });
    if (states.wool_cheque_bonus) stateBadges.push({
      label: `Wool bonus ${states.wool_cheque_bonus >= 0 ? "+" : ""}$${states.wool_cheque_bonus}`,
      color: states.wool_cheque_bonus >= 0 ? "#388e3c" : "#d32f2f",
    });
    if (states.visiting_town_turns > 0) stateBadges.push({ label: `Visiting town: miss ${states.visiting_town_turns} turn(s)`, color: "#6a4c93" });

    return (
      <>
        {financials && (
          <section style={{
            marginBottom: "0.8rem", padding: "8px 12px", borderRadius: 6,
            background: "#f5f0e8", border: "1px solid #d4c5a3",
          }}>
            <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.95rem", color: "#555" }}>Finances</h3>
            {finRow("Cash held", money(fin.cash), { bold: true, color: fin.cash < 0 ? "#d32f2f" : "#1b5e20" })}
            {finRow("Sheep", `${fin.sheep_pens} pens (${(fin.sheep_count ?? 0).toLocaleString()} head)`)}
            {finRow("Paddocks", `${fin.paddocks_owned}${fin.paddocks_mortgaged ? ` (${fin.paddocks_mortgaged} mortgaged)` : ""}`)}
            {finRow("Stud rams", fin.stud_rams)}
            {finRow("Haystack", fin.has_haystack ? "Yes" : "No")}
            <div style={{ borderTop: "1px solid #d4c5a3", margin: "5px 0" }} />
            {finRow("Liquidation value", money(fin.liquidation_value),
              { color: "#555" })}
            {finRow("Net worth", money(fin.net_worth),
              { bold: true, color: fin.net_worth < 0 ? "#d32f2f" : "#1b5e20" })}
          </section>
        )}

        <section style={{ marginBottom: "0.8rem" }}>
          <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.95rem", color: "#555" }}>
            Paddocks ({totalPens}/{totalCap} pens)
          </h3>
          {paddocks.length === 0 ? (
            <p style={{ margin: 0, fontSize: "0.85rem", color: "#888" }}>None</p>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {paddocks.map((p) => (
                <li key={p.paddock_number} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "5px 10px", marginBottom: 4, borderRadius: 4,
                  background: "#fafafa", borderLeft: `4px solid ${TYPE_COLOR[p.paddock_type]}`,
                  opacity: p.is_mortgaged ? 0.55 : 1,
                }}>
                  <span style={{ fontSize: "0.85rem" }}>
                    <strong>#{p.paddock_number}</strong>{" "}
                    <span style={{ color: TYPE_COLOR[p.paddock_type] }}>{TYPE_LABEL[p.paddock_type]}</span>
                    {p.is_mortgaged && <span style={{ marginLeft: 4, color: "#d32f2f", fontSize: "0.75rem" }}>(mortgaged)</span>}
                  </span>
                  <span style={{ fontSize: "0.85rem", fontFamily: "monospace" }}>
                    {p.sheep_pens}/{p.max_pens}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section style={{ marginBottom: "0.8rem" }}>
          <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.95rem", color: "#555" }}>
            Stud Rams ({studRams.length})
          </h3>
          {studRams.length === 0 ? (
            <p style={{ margin: 0, fontSize: "0.85rem", color: "#888" }}>None</p>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {studRams.map((r) => (
                <li key={r.space_id} style={{
                  marginBottom: 6, padding: "8px 10px", borderRadius: 6,
                  background: "#e8f5e9", border: "1px solid #a5d6a7",
                }}>
                  <div style={{ fontWeight: "bold", fontSize: "0.9rem" }}>{r.space_name}</div>
                  <div style={{ fontSize: "0.75rem", color: "#666" }}>Stud fee: ${r.stud_fee}</div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section style={{ marginBottom: "0.8rem" }}>
          <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.95rem", color: "#555" }}>
            Cards ({cards.length})
          </h3>
          {cards.length === 0 ? (
            <p style={{ margin: 0, fontSize: "0.85rem", color: "#888" }}>None</p>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {cards.map((c) => (
                <li key={c.card_draw_id}
                  onClick={() => onCardClick?.(c)}
                  style={{
                    marginBottom: 6, padding: "8px 10px", borderRadius: 6,
                    background: "#f5f0e8", border: "1px solid #d4c5a3",
                    cursor: onCardClick ? "pointer" : "default",
                  }}>
                  <div style={{ fontWeight: "bold", fontSize: "0.9rem", color: "#6a4c93" }}>
                    {c.title}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#666", marginTop: 2 }}>
                    {c.deck_type === "tucker_bag" ? "Tucker Bag" : "Expense Immunity"}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {stateBadges.length > 0 && (
          <section>
            <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.95rem", color: "#555" }}>Status</h3>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {stateBadges.map((b, i) => (
                <span key={i} style={{
                  fontSize: "0.75rem", padding: "3px 7px", borderRadius: 4,
                  background: b.color, color: "#fff",
                }}>{b.label}</span>
              ))}
            </div>
          </section>
        )}
      </>
    );
  };

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        <button style={closeBtn} onClick={onClose} aria-label="Close">×</button>
        <h2 style={{ margin: "0 0 0.8rem", fontSize: "1.15rem" }}>
          {playerName ? `${playerName}'s Station` : "Station"}
          {holdings && holdings.is_active === false && (
            <span style={{
              marginLeft: 8, padding: "2px 8px", borderRadius: 4,
              background: "#424242", color: "#fff", fontSize: "0.7rem", fontWeight: "bold",
              verticalAlign: "middle",
            }}>BANKRUPT</span>
          )}
        </h2>
        {renderBody()}
      </div>
    </div>
  );
}
