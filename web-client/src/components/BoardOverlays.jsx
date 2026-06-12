const API_BASE = import.meta.env.VITE_API_BASE || '';

/* Board-anchored overlays (rendered inside the board container, below the
   SQUATTER title) for pendings that show a card rather than a centred
   modal: the revealed Stock Sale card and the drawn Tucker Bag card. */

function overlayHelpers({ gameId, sessionToken, pendingAction, players, userId, onResolved }) {
  const activeIsMe = players.some(
    p => p.game_player_id === pendingAction.active_player_id && p.user_id === userId
  );
  const activeName = players.find(
    p => p.game_player_id === pendingAction.active_player_id
  )?.player_name;
  const post = async (path, body) => {
    try {
      await fetch(`${API_BASE}/games/${gameId}/${path}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${sessionToken}`, 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body || {}),
      });
      onResolved();
    } catch { /* surfacing handled by next poll */ }
  };
  return { activeIsMe, activeName, post };
}

/* Renders for any pending action whose data carries a Stock Sale card
   snapshot (stock_sale_result, tucker_bag_result with card, drought_effect
   with haystack-drawn card, etc.). Returns null otherwise. */
export function StockSaleCardOverlay(props) {
  const { pendingAction } = props;
  if (!pendingAction) return null;
  const sd = pendingAction.action_data || {};
  const at = pendingAction.action_type;
  const overlayTypes = ['stock_sale_result', 'tucker_bag_result', 'drought_effect'];
  const hasCard = !!(sd.card || sd.stock_card_used);
  if (!overlayTypes.includes(at) || !hasCard) return null;

  const { activeIsMe, activeName, post } = overlayHelpers(props);
  const card = sd.card || sd.stock_card_used || {};
  const isStockResult = at === 'stock_sale_result';
  const isBuy = sd.action === 'buy';
  const titleByType = {
    stock_sale_result: 'Stock Sale — Card Revealed',
    tucker_bag_result: `${sd.card_title || 'Tucker Bag'} — Stock Sale Card`,
    drought_effect: 'Local Drought — Stock Sale Card (Haystack)',
  };

  return (
    <div style={{
      position: "absolute", top: "600px", left: "50%", transform: "translateX(-50%)",
      background: "#fff", border: "2px solid #1982c4", borderRadius: 10,
      padding: "14px 18px", boxShadow: "0 4px 12px rgba(0,0,0,0.2)", zIndex: 3,
      width: 360,
    }}>
      <h3 style={{ margin: "0 0 8px", color: "#1982c4", fontSize: "1rem", textAlign: "center" }}>
        {titleByType[at] || 'Stock Sale Card'}
      </h3>
      <div style={{ padding: "8px", background: "#E3F2FD", borderRadius: 6, fontSize: "0.85rem" }}>
        <table style={{ width: "100%" }}>
          <tbody>
            {card.buy_price_per_pen !== undefined && (
              <tr><td>Buy</td><td style={{ textAlign: "right" }}><strong>${card.buy_price_per_pen}/pen</strong></td></tr>
            )}
            <tr><td>Sell — Natural</td><td style={{ textAlign: "right" }}><strong>${card.sell_price_natural}/pen</strong></td></tr>
            <tr><td>Sell — Improved/Irrigated</td><td style={{ textAlign: "right" }}><strong>${card.sell_price_improved_irrigated}/pen</strong></td></tr>
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, padding: "8px", background: "#F1F8E9", borderRadius: 6, fontSize: "0.85rem" }}>
        {isStockResult ? (
          isBuy ? (
            <>Bought <strong>{sd.pens}</strong> pens at <strong>${sd.buy_price}/pen</strong> = <strong>${sd.total_cost}</strong></>
          ) : (
            <>Sold <strong>{sd.pens}</strong> pens for <strong>${sd.total_income}</strong>
              {Array.isArray(sd.tiers) && sd.tiers.some(([, n]) => n > 0) && (
                <div style={{ fontSize: "0.78rem", color: "#666", marginTop: 4 }}>
                  {sd.tiers.filter(([, n]) => n > 0).map(([t, n]) => `${n} ${t}`).join(', ')}
                </div>
              )}
            </>
          )
        ) : (
          <>Sold <strong>{sd.pens_sold}</strong> pens for <strong>${sd.income}</strong>
            {sd.by_type && (
              <div style={{ fontSize: "0.78rem", color: "#666", marginTop: 4 }}>
                {Object.entries(sd.by_type).filter(([, n]) => n > 0).map(([t, n]) => `${n} ${t}`).join(', ')}
              </div>
            )}
            {sd.haystack_lost && (
              <div style={{ fontSize: "0.78rem", color: "#b71c1c", marginTop: 4 }}>
                Haystack lost (returned to Bank).
              </div>
            )}
            {sd.restock_blocked && (
              <div style={{ fontSize: "0.78rem", color: "#E65100", marginTop: 4, fontWeight: "bold" }}>
                Restock blocked until full circuit.
              </div>
            )}
          </>
        )}
      </div>
      {activeIsMe && (
        <div style={{ textAlign: "center", marginTop: 10 }}>
          <button onClick={() => post('decisions/acknowledge')} style={{
            padding: "0.5rem 1.2rem", background: "#1982c4", color: "#fff",
            border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold"
          }}>OK</button>
        </div>
      )}
      {!activeIsMe && (
        <p style={{ fontSize: "0.78rem", color: "#666", textAlign: "center", margin: "8px 0 0", fontStyle: "italic" }}>
          Waiting for {activeName}...
        </p>
      )}
    </div>
  );
}

export function TuckerBagDrawOverlay(props) {
  const { pendingAction } = props;
  if (!pendingAction || pendingAction.action_type !== 'tucker_bag_drawn') return null;

  const { activeIsMe, activeName, post } = overlayHelpers(props);
  const sd = pendingAction.action_data || {};

  return (
    <div style={{
      position: "absolute", top: "600px", left: "50%", transform: "translateX(-50%)",
      background: "#fff", border: "2px solid #6a4c93", borderRadius: 10,
      padding: "14px 18px", boxShadow: "0 4px 12px rgba(0,0,0,0.2)", zIndex: 3,
      width: 380,
    }}>
      <h3 style={{ margin: "0 0 4px", color: "#6a4c93", fontSize: "1rem", textAlign: "center" }}>
        Tucker Bag
      </h3>
      <h4 style={{ margin: "0 0 6px", textAlign: "center" }}>{sd.title}</h4>
      <p style={{ color: "#555", lineHeight: 1.4, fontSize: "0.85rem", margin: 0 }}>{sd.body_text}</p>
      {sd.tax_breakdown && (
        <div style={{ marginTop: "0.6rem", padding: "0.6rem", background: "#f5f5f5", borderRadius: 6, border: "1px solid #ddd" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
            <tbody>
              {sd.tax_breakdown.lines.map((line, i) => (
                <tr key={i}>
                  <td style={{ padding: "0.2rem 0" }}>{line.label}</td>
                  <td style={{ padding: "0.2rem 0.5rem", color: "#666", textAlign: "right" }}>
                    {line.rate_label || `@ $${line.rate}`}
                  </td>
                  <td style={{ padding: "0.2rem 0", textAlign: "right", fontWeight: 500 }}>${line.amount.toLocaleString()}</td>
                </tr>
              ))}
              <tr style={{ borderTop: "2px solid #999" }}>
                <td colSpan={2} style={{ padding: "0.3rem 0", fontWeight: "bold" }}>Total Tax</td>
                <td style={{ padding: "0.3rem 0", textAlign: "right", fontWeight: "bold", color: "#d32f2f" }}>
                  ${sd.tax_breakdown.total.toLocaleString()}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
      {sd.is_retainable && (
        <p style={{ color: "#4caf50", fontWeight: "bold", fontSize: "0.85rem", marginTop: "0.5rem" }}>
          This card can be kept!
        </p>
      )}
      {(sd.haystack_offers || []).length > 0 && (
        <div style={{ marginTop: "0.5rem", padding: "0.6rem", background: "#F1F8E9", border: "1px solid #7CB342", borderRadius: 6, fontSize: "0.82rem" }}>
          <div>
            <strong style={{ color: "#33691E" }}>Haymaking Season!</strong>
            {sd.haystack_drought_premium && (
              <span style={{ marginLeft: 6, color: "#b71c1c", fontSize: "0.78rem" }}>(drought premium)</span>
            )}
          </div>
          {activeIsMe && (
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
              {sd.haystack_offers.map((o) => (
                <button key={o.type}
                  onClick={() => post('station/buy-haystack', { haystack_type: o.type })}
                  style={{
                    padding: "0.4rem 0.9rem", background: "#7CB342", color: "#fff",
                    border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold", fontSize: "0.82rem"
                  }}>
                  Buy {o.type === 'pasture' ? 'Pasture' : 'Irrigated'} Haystack (${o.cost})
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {activeIsMe && (
        <div style={{ display: "flex", gap: "0.5rem", marginTop: 10, flexWrap: "wrap", justifyContent: "center" }}>
          {sd.is_retainable && sd.purchase_price > 0 ? (
            <>
              <button onClick={() => post('decisions/tucker-bag', { buy_card: true })} style={{
                padding: "0.5rem 1.2rem", background: "#4caf50", color: "#fff",
                border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold"
              }}>Buy (${sd.purchase_price})</button>
              <button onClick={() => post('decisions/tucker-bag', { buy_card: false })} style={{
                padding: "0.5rem 1.2rem", background: "#666", color: "#fff",
                border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold"
              }}>Decline</button>
            </>
          ) : (
            <button onClick={() => post('decisions/tucker-bag', { buy_card: !!sd.is_retainable })} style={{
              padding: "0.5rem 1.2rem", background: "#6a4c93", color: "#fff",
              border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold"
            }}>{sd.is_retainable ? 'Keep Card' : 'OK'}</button>
          )}
        </div>
      )}
      {!activeIsMe && (
        <p style={{ fontSize: "0.78rem", color: "#666", textAlign: "center", margin: "8px 0 0", fontStyle: "italic" }}>
          Waiting for {activeName}...
        </p>
      )}
    </div>
  );
}
