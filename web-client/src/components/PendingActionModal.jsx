import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function PendingActionModal({ gameId, sessionToken, userId, pendingAction, players, onResolved, activePlayerHasHighStockPrices = false }) {
  const [pens, setPens] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [useHighStockPrices, setUseHighStockPrices] = useState(false);

  if (!pendingAction) return null;

  const activePlayer = players.find(p => p.game_player_id === pendingAction.active_player_id);
  const isMyAction = activePlayer && activePlayer.user_id === userId;
  const data = pendingAction.action_data || {};

  const headers = {
    'Authorization': `Bearer ${sessionToken}`,
    'Content-Type': 'application/json'
  };

  const doAction = async (endpoint, body = {}) => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/games/${gameId}/${endpoint}`, {
        method: 'POST', headers, body: JSON.stringify(body)
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload.detail || `Failed: ${res.status}`);
      }
      // Stock Sale buy with insufficient funds: card stays drawn, pending
      // stays open in committed mode — surface the message and refresh so
      // the modal re-renders with the lock state.
      if (payload.status === 'insufficient_funds') {
        setError(
          `Cannot afford ${payload.requested_pens} pens at the locked price ` +
          `(balance $${payload.balance}). Try fewer pens or pass.`
        );
        onResolved();
        return;
      }
      onResolved();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const modalStyle = {
    position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
    background: '#fff', borderRadius: '12px', padding: '2rem', minWidth: '380px',
    maxWidth: '500px', boxShadow: '0 10px 40px rgba(0,0,0,0.3)', zIndex: 9000
  };

  const btnStyle = (bg) => ({
    padding: '0.6rem 1.2rem', background: bg, color: '#fff',
    border: 'none', borderRadius: '6px', cursor: submitting ? 'not-allowed' : 'pointer',
    fontSize: '0.95rem', fontWeight: 'bold', opacity: submitting ? 0.6 : 1
  });

  const haystackOfferBlock = data.haystack_available ? (
    <div style={{ marginTop: '0.5rem', padding: '0.6rem', background: '#F1F8E9', border: '1px solid #7CB342', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
      <div style={{ flex: 1 }}>
        <strong style={{ color: '#33691E' }}>Haymaking Season!</strong>
        <span style={{ marginLeft: '0.5rem', fontSize: '0.9rem' }}>Haystack available for ${data.haystack_cost}</span>
        {data.haystack_drought_premium && (
          <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: '#b71c1c', fontWeight: 'bold' }}>
            (drought premium — normally $500)
          </span>
        )}
      </div>
      {isMyAction && (
        <button style={btnStyle('#7CB342')} disabled={submitting}
          onClick={() => doAction('station/buy-haystack', {})}>
          Buy Haystack (${data.haystack_cost})
        </button>
      )}
    </div>
  ) : null;

  // No-op now — kept for backwards compatibility with existing JSX references.
  // The Buy Haystack button is rendered inline inside haystackOfferBlock above.
  const haystackBuyButton = null;

  // Stock Sale — DECLARE step (no card visible yet, per rules)
  if (pendingAction.action_type === 'stock_sale_decision') {
    const buyCommitted = !!data.buy_committed;
    const originalPens = data.original_pens ?? 0;
    const hspLocked = !!data.hsp_locked;
    const maxBuy = buyCommitted
      ? Math.min(originalPens, data.empty_pens ?? 15, data.max_per_transaction ?? 15)
      : Math.min(data.empty_pens ?? 15, data.max_per_transaction ?? 15);
    const maxSell = Math.min(data.total_pens ?? 0, data.max_per_transaction ?? 15);
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 1rem', color: '#1982c4' }}>
          {buyCommitted ? 'Stock Sale — Buy Locked' : 'Stock Sale — Declare'}
        </h2>
        <p><strong>{data.space_name || 'Stock Sale'}</strong></p>
        {buyCommitted ? (
          <div style={{ marginBottom: '0.5rem', padding: '0.6rem', background: '#FFF3E0', border: '1px solid #FB8C00', borderRadius: '6px', fontSize: '0.85rem', color: '#E65100' }}>
            You committed to buy <strong>{originalPens}</strong> pens. The Stock Sale
            card has been drawn but stays hidden; the price is locked. Choose a
            smaller number of pens or pass.
          </div>
        ) : (
          <p style={{ fontSize: '0.85rem', color: '#666', fontStyle: 'italic' }}>
            Per the rules, you must commit to buy/sell and the number of pens
            <strong> before</strong> the Stock Sale card is revealed.
          </p>
        )}
        <p style={{ fontSize: '0.85rem' }}>
          You hold <strong>{data.total_pens ?? '?'}</strong> pens; <strong>{data.empty_pens ?? '?'}</strong> empty pens of capacity available.
        </p>
        {data.in_drought && (
          <div style={{ marginTop: '0.5rem', padding: '0.5rem', background: '#FFEBEE', border: '1px solid #d32f2f', borderRadius: '6px', fontSize: '0.85rem', color: '#b71c1c' }}>
            <strong>Drought rules apply:</strong>
            <ul style={{ margin: '4px 0 0 1rem', padding: 0 }}>
              <li>Buying restricted to <strong>Irrigated</strong> capacity only ({data.empty_irrigated_pens ?? 0} pens free).</li>
              <li>Selling from Natural or Improved is at <strong>half price</strong>; Irrigated sells at full price.</li>
            </ul>
          </div>
        )}
        {data.restock_blocked && (
          <div style={{ marginTop: '0.5rem', padding: '0.5rem', background: '#FFF3E0', border: '1px solid #FF9800', borderRadius: '6px', fontSize: '0.85rem', color: '#E65100' }}>
            <strong>Restock blocked.</strong>{' '}
            You cannot buy stock until the circuit is complete
            {data.restock_block_spaces_remaining > 0 && (
              <> ({data.restock_block_spaces_remaining} spaces remaining)</>
            )}. Selling and passing are still allowed.
          </div>
        )}
        {isMyAction && activePlayerHasHighStockPrices && (
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.5rem', padding: '0.5rem', background: '#FFF8E1', border: '1px solid #FFB300', borderRadius: '6px', opacity: buyCommitted ? 0.7 : 1 }}>
            <input type="checkbox"
              checked={buyCommitted ? hspLocked : useHighStockPrices}
              disabled={buyCommitted}
              onChange={(e) => setUseHighStockPrices(e.target.checked)} />
            <span style={{ fontSize: '0.9rem' }}>
              Apply <strong>High Stock Prices</strong> (+20% to buy or sell — discards card)
              {buyCommitted && <em style={{ marginLeft: 6, color: '#666' }}>(locked)</em>}
            </span>
          </label>
        )}
        {haystackOfferBlock}
        {isMyAction && (
          <div style={{ marginTop: '1rem' }}>
            <label>Pens: <input type="number" min={1} max={buyCommitted ? maxBuy : (data.max_per_transaction ?? 15)} value={pens} onChange={e => setPens(Number(e.target.value))} style={{ width: 60, marginLeft: 8 }} /></label>
            <span style={{ marginLeft: 12, fontSize: '0.78rem', color: '#666' }}>
              max buy {maxBuy}{!buyCommitted && <>, max sell {maxSell}</>}
            </span>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
              <button style={btnStyle('#4caf50')} disabled={submitting || pens > maxBuy || pens < 1 || !!data.restock_blocked}
                title={data.restock_blocked ? 'Restock blocked — complete the circuit first' : undefined}
                onClick={() => doAction('decisions/stock-sale', { action: 'buy', pens, use_high_stock_prices: useHighStockPrices })}>Buy {pens}</button>
              {!buyCommitted && (
                <button style={btnStyle('#ff9800')} disabled={submitting || pens > maxSell || pens < 1}
                  onClick={() => doAction('decisions/stock-sale', { action: 'sell', pens, use_high_stock_prices: useHighStockPrices })}>Sell {pens}</button>
              )}
              <button style={btnStyle('#666')} disabled={submitting} onClick={() => doAction('decisions/stock-sale', { action: 'pass' })}>Pass</button>
              {haystackBuyButton}
            </div>
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Stock Sale — RESULT step is rendered inline inside the board container in App.jsx
  // (anchored below the SQUATTER title), not as a centred modal.
  if (pendingAction.action_type === 'stock_sale_result') {
    return null;
  }

  // (legacy modal block left for reference but unreachable)
  // eslint-disable-next-line no-unreachable
  if (false && pendingAction.action_type === 'stock_sale_result') {
    const card = data.card || {};
    const isBuy = data.action === 'buy';
    const stockResultStyle = {
      ...modalStyle,
      top: '600px', left: '20px', transform: 'none',
      minWidth: '320px', maxWidth: '420px',
    };
    return (
      <div style={stockResultStyle}>
        <h2 style={{ margin: '0 0 1rem', color: '#1982c4' }}>Stock Sale — Card Revealed</h2>
        <div style={{ padding: '0.75rem', background: '#E3F2FD', border: '1px solid #1982c4', borderRadius: 6 }}>
          <strong>Stock Sale Card</strong>
          <table style={{ width: '100%', marginTop: 6, fontSize: '0.85rem' }}>
            <tbody>
              <tr><td>Buy price (per pen)</td><td style={{ textAlign: 'right' }}><strong>${card.buy_price_per_pen}</strong></td></tr>
              <tr><td>Sell — Natural</td><td style={{ textAlign: 'right' }}><strong>${card.sell_price_natural}</strong></td></tr>
              <tr><td>Sell — Improved / Irrigated</td><td style={{ textAlign: 'right' }}><strong>${card.sell_price_improved_irrigated}</strong></td></tr>
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: '0.75rem', padding: '0.6rem', background: '#F1F8E9', border: '1px solid #7CB342', borderRadius: 6 }}>
          {isBuy ? (
            <>
              You bought <strong>{data.pens}</strong> pens at <strong>${data.buy_price}/pen</strong> = <strong>${data.total_cost}</strong>
              {data.high_stock_prices_applied && <div style={{ fontSize: '0.8rem', color: '#E65100' }}>High Stock Prices +20% applied</div>}
            </>
          ) : (
            <>
              You sold <strong>{data.pens}</strong> pens for <strong>${data.total_income}</strong>
              {Array.isArray(data.tiers) && data.tiers.some(([, n]) => n > 0) && (
                <div style={{ fontSize: '0.78rem', color: '#666', marginTop: 4 }}>
                  Breakdown: {data.tiers.filter(([, n]) => n > 0).map(([t, n]) => `${n} ${t}`).join(', ')}
                </div>
              )}
              {data.modifier_pct ? <div style={{ fontSize: '0.8rem', color: '#E65100' }}>+{data.modifier_pct}% modifier applied</div> : null}
              {data.in_drought && <div style={{ fontSize: '0.8rem', color: '#b71c1c' }}>Drought: Natural/Improved sold at half price</div>}
            </>
          )}
        </div>
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <button style={btnStyle('#1982c4')} disabled={submitting}
              onClick={() => doAction('decisions/acknowledge')}>OK</button>
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Stud Ram Purchase
  if (pendingAction.action_type === 'stud_ram_purchase') {
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 1rem', color: '#795548' }}>Stud Ram Available</h2>
        <p><strong>{data.space_name}</strong></p>
        <p>Purchase price: <strong>${data.purchase_price}</strong></p>
        <p>Stud fee earned: <strong>${data.stud_fee}/visit</strong></p>
        {haystackOfferBlock}
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            <button style={btnStyle('#4caf50')} disabled={submitting} onClick={() => doAction('decisions/stud-ram-buy')}>Buy (${data.purchase_price})</button>
            <button style={btnStyle('#666')} disabled={submitting} onClick={() => doAction('decisions/stud-ram-pass')}>Pass</button>
            {haystackBuyButton}
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Tucker Bag Card — rendered as an inline overlay on the board (in App.jsx).
  if (pendingAction.action_type === 'tucker_bag_drawn') {
    return null;
  }

  // eslint-disable-next-line no-unreachable
  if (false && pendingAction.action_type === 'tucker_bag_drawn') {
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 0.5rem', color: '#6a4c93' }}>Tucker Bag</h2>
        <h3 style={{ margin: '0 0 0.5rem' }}>{data.title}</h3>
        <p style={{ color: '#555', lineHeight: 1.5 }}>{data.body_text}</p>
        {data.tax_breakdown && (
          <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#f5f5f5', borderRadius: '6px', border: '1px solid #ddd' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
              <tbody>
                {data.tax_breakdown.lines.map((line, i) => (
                  <tr key={i}>
                    <td style={{ padding: '0.25rem 0' }}>{line.label}</td>
                    <td style={{ padding: '0.25rem 0.5rem', color: '#666', textAlign: 'right' }}>
                      {line.rate_label || `@ $${line.rate}`}
                    </td>
                    <td style={{ padding: '0.25rem 0', textAlign: 'right', fontWeight: '500' }}>${line.amount.toLocaleString()}</td>
                  </tr>
                ))}
                <tr style={{ borderTop: '2px solid #999' }}>
                  <td colSpan={2} style={{ padding: '0.4rem 0', fontWeight: 'bold' }}>Total Tax</td>
                  <td style={{ padding: '0.4rem 0', textAlign: 'right', fontWeight: 'bold', color: '#d32f2f' }}>${data.tax_breakdown.total.toLocaleString()}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
        {data.is_retainable && <p style={{ color: '#4caf50', fontWeight: 'bold' }}>This card can be kept!</p>}
        {haystackOfferBlock}
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            <button style={btnStyle('#6a4c93')} disabled={submitting}
              onClick={() => doAction('decisions/tucker-bag', { buy_card: data.is_retainable })}>
              {data.is_retainable ? 'Keep Card' : 'OK'}
            </button>
            {haystackBuyButton}
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Fire Fighting Equipment offer (after the active player declined)
  if (pendingAction.action_type === 'fire_fighting_offer') {
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 0.5rem', color: '#d84315' }}>Fire Fighting Equipment Offered</h2>
        <h3 style={{ margin: '0 0 0.5rem' }}>{data.card_title}</h3>
        <p style={{ color: '#555', lineHeight: 1.4, fontSize: '0.9rem' }}>{data.card_body}</p>
        <p>The active player declined. You may purchase it for <strong>${data.price}</strong>.</p>
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <button style={btnStyle('#4caf50')} disabled={submitting}
              onClick={() => doAction('decisions/fire-fighting-offer', { accept: true })}>
              Accept (${data.price})
            </button>
            <button style={btnStyle('#666')} disabled={submitting}
              onClick={() => doAction('decisions/fire-fighting-offer', { accept: false })}>
              Decline
            </button>
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Stud Fee Paid
  if (pendingAction.action_type === 'stud_fee_paid') {
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 1rem', color: '#795548' }}>Stud Fee Paid</h2>
        <p>Paid <strong>${data.amount}</strong> stud fee to <strong>{data.owner_name}</strong> for {data.ram_name}.</p>
        {haystackOfferBlock}
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            <button style={btnStyle('#1982c4')} disabled={submitting} onClick={() => doAction('decisions/acknowledge')}>OK</button>
            {haystackBuyButton}
          </div>
        )}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Expense Payment (with optional card purchase or alternative-payment choice)
  if (pendingAction.action_type === 'expense_payment') {
    // Drench Sheep for Worms — two mutually-exclusive payment options
    if (data.alternative_payment) {
      return (
        <div style={modalStyle}>
          <h2 style={{ margin: '0 0 1rem', color: '#e65100' }}>{data.space_name}</h2>
          <p>Choose your treatment ({data.total_pens} pens):</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.75rem' }}>
            <div style={{ padding: '0.75rem', background: '#FFF8E1', border: '1px solid #FFB300', borderRadius: '6px' }}>
              <strong>{data.basic_option.label}</strong>
              <div style={{ fontSize: '0.85rem', color: '#666' }}>
                ${data.basic_option.rate_per_pen}/pen × {data.total_pens} pens = <strong>${data.basic_option.cost}</strong>
              </div>
            </div>
            <div style={{ padding: '0.75rem', background: '#E8F5E9', border: '1px solid #66BB6A', borderRadius: '6px' }}>
              <strong>{data.enhanced_option.label}</strong>
              <div style={{ fontSize: '0.85rem', color: '#666' }}>
                ${data.enhanced_option.rate_per_pen}/pen × {data.total_pens} pens = <strong>${data.enhanced_option.cost}</strong>
              </div>
            </div>
          </div>
          {haystackOfferBlock}
          {isMyAction && (
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
              <button style={btnStyle('#FFB300')} disabled={submitting}
                onClick={() => doAction('decisions/expense', { option: 'basic' })}>
                Pay ${data.basic_option.cost} (basic)
              </button>
              <button style={btnStyle('#388e3c')} disabled={submitting}
                onClick={() => doAction('decisions/expense', { option: 'enhanced' })}>
                Pay ${data.enhanced_option.cost} (Worm Control +20%)
              </button>
              {haystackBuyButton}
            </div>
          )}
          {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666' }}>Waiting for {activePlayer?.player_name}...</p>}
          {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
        </div>
      );
    }

    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 1rem', color: '#e65100' }}>Expense</h2>
        <p><strong>{data.space_name}</strong></p>
        {data.has_card ? (
          <p style={{ color: '#4caf50', fontWeight: 'bold' }}>You hold the immunity card — no charge!</p>
        ) : (
          <>
            <p>Cost: <strong>${data.total_cost}</strong>
              {data.cost_per_pen > 0 && <span style={{ color: '#666', fontSize: '0.85rem' }}> ({data.total_pens} pens × ${data.cost_per_pen}/pen)</span>}
            </p>
            {data.card_granted && (
              <p style={{ color: '#4caf50', fontWeight: 'bold', marginTop: '0.5rem' }}>
                Received: {data.card_granted} (immunity from future charges here)
              </p>
            )}
          </>
        )}
        {haystackOfferBlock}
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            <button style={btnStyle('#1982c4')} disabled={submitting}
              onClick={() => doAction('decisions/expense', { buy_card: false })}>OK</button>
            {haystackBuyButton}
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Wool Cheque Paid — informational popup so the player can see the breakdown
  if (pendingAction.action_type === 'wool_cheque_paid') {
    const perPen = data.per_pen_rate ?? 250;
    const ramPerPen = data.per_pen_per_ram_rate ?? 25;
    const totalPens = data.total_pens ?? 0;
    const studRams = data.stud_rams ?? 0;
    const baseAmount = data.base_amount ?? 0;
    const ramBonus = data.ram_bonus ?? 0;
    const extraBonus = data.extra_bonus ?? 0;
    const blowflyReduction = data.blowfly_reduction ?? 0;
    const total = data.total ?? 0;
    const interest = data.mortgage_interest ?? 0;
    const net = total - interest;
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 0.5rem', color: '#1982c4' }}>Wool Sale</h2>
        <p style={{ margin: '0 0 0.75rem', color: '#555', fontSize: '0.9rem' }}>
          {data.trigger === 'card' ? 'Moved to Wool Sale by card.'
            : data.trigger === 'passed' ? 'Passed Wool Sale.'
            : 'Landed on Wool Sale.'}
        </p>
        <table style={{ width: '100%', fontSize: '0.9rem', borderCollapse: 'collapse' }}>
          <tbody>
            <tr>
              <td style={{ padding: '0.25rem 0' }}>{totalPens} pens × ${perPen}/pen</td>
              <td style={{ padding: '0.25rem 0', textAlign: 'right' }}>${baseAmount.toLocaleString()}</td>
            </tr>
            {studRams > 0 && (
              <tr>
                <td style={{ padding: '0.25rem 0' }}>
                  Stud ram bonus ({studRams} ram{studRams > 1 ? 's' : ''} × {totalPens} pens × ${ramPerPen})
                </td>
                <td style={{ padding: '0.25rem 0', textAlign: 'right' }}>${ramBonus.toLocaleString()}</td>
              </tr>
            )}
            {extraBonus > 0 && (
              <tr>
                <td style={{ padding: '0.25rem 0' }}>Card bonus</td>
                <td style={{ padding: '0.25rem 0', textAlign: 'right' }}>${extraBonus.toLocaleString()}</td>
              </tr>
            )}
            {blowflyReduction > 0 && (
              <tr>
                <td style={{ padding: '0.25rem 0', color: '#b71c1c' }}>Blowfly penalty</td>
                <td style={{ padding: '0.25rem 0', textAlign: 'right', color: '#b71c1c' }}>−${blowflyReduction.toLocaleString()}</td>
              </tr>
            )}
            <tr style={{ borderTop: '1px solid #ccc' }}>
              <td style={{ padding: '0.4rem 0', fontWeight: 'bold' }}>Wool cheque</td>
              <td style={{ padding: '0.4rem 0', textAlign: 'right', fontWeight: 'bold', color: '#2e7d32' }}>
                ${total.toLocaleString()}
              </td>
            </tr>
            {interest > 0 && (
              <>
                <tr>
                  <td style={{ padding: '0.25rem 0', color: '#b71c1c' }}>Mortgage interest</td>
                  <td style={{ padding: '0.25rem 0', textAlign: 'right', color: '#b71c1c' }}>−${interest.toLocaleString()}</td>
                </tr>
                <tr style={{ borderTop: '1px solid #ccc' }}>
                  <td style={{ padding: '0.4rem 0', fontWeight: 'bold' }}>Net to player</td>
                  <td style={{ padding: '0.4rem 0', textAlign: 'right', fontWeight: 'bold' }}>${net.toLocaleString()}</td>
                </tr>
              </>
            )}
          </tbody>
        </table>
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
            <button style={btnStyle('#1982c4')} disabled={submitting}
              onClick={() => doAction('decisions/acknowledge')}>OK</button>
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666', marginTop: '0.75rem' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Haystack Offer (Haymaking landings with no other pending action)
  if (pendingAction.action_type === 'haystack_offer') {
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 1rem', color: '#33691E' }}>Haymaking Season</h2>
        <p><strong>{data.space_name}</strong></p>
        <p>You may purchase a haystack for <strong>${data.haystack_cost}</strong>.</p>
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            {haystackBuyButton}
            <button style={btnStyle('#666')} disabled={submitting}
              onClick={() => doAction('decisions/acknowledge')}>Skip</button>
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Pending actions whose data carries a Stock Sale card (drought_effect with
  // haystack draw, tucker_bag_result for Grass Fire, etc.) are rendered as an
  // inline overlay anchored to the board (in App.jsx). Suppress the centred
  // modal version for those.
  if ((pendingAction.action_type === 'drought_effect' && data.stock_card_used)
      || (pendingAction.action_type === 'tucker_bag_result' && data.stock_card_used)) {
    return null;
  }

  // Local Drought — detailed breakdown
  if (pendingAction.action_type === 'drought_effect') {
    // Haystack-with-card variant is rendered as an inline overlay on the board.
    if (data.stock_card_used) return null;

    const noEffect = data.no_effect;
    const pensSold = data.pens_sold ?? 0;
    const income = data.income ?? 0;
    const droughtSpaces = data.drought_spaces ?? 0;
    const extended = !!data.extended;
    const byType = data.by_type;
    const pricePerPen = data.no_haystack_price_per_pen;
    const hadHaystack = !!data.had_haystack;
    const haystackPreserved = pensSold === 0 && hadHaystack;
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 0.5rem', color: '#d32f2f' }}>Local Drought!</h2>
        {data.space_name && <p style={{ margin: '0 0 0.75rem' }}><strong>{data.space_name}</strong></p>}
        {noEffect ? (
          <p style={{ color: '#388e3c', fontWeight: 'bold' }}>
            {data.reason || 'No effect — your station is all Irrigated.'}
          </p>
        ) : (
          <>
            <p style={{ fontSize: '0.85rem', color: '#666', fontStyle: 'italic', margin: '0 0 0.75rem' }}>
              Half of your Natural/Improved stock (rounded up) is sold to the Bank.
              Irrigated stock is not affected. While in drought you may only restock
              into Irrigated paddocks, and cannot upgrade paddocks or sell stud rams.
            </p>
            {pensSold > 0 ? (
              <table style={{ width: '100%', fontSize: '0.9rem', borderCollapse: 'collapse' }}>
                <tbody>
                  <tr>
                    <td style={{ padding: '0.25rem 0' }}>Pens sold (Natural/Improved)</td>
                    <td style={{ padding: '0.25rem 0', textAlign: 'right' }}><strong>{pensSold}</strong></td>
                  </tr>
                  {byType && Object.values(byType).some(n => n > 0) && (
                    <tr>
                      <td style={{ padding: '0.1rem 0 0.25rem 0', fontSize: '0.78rem', color: '#666' }} colSpan={2}>
                        {Object.entries(byType).filter(([, n]) => n > 0).map(([t, n]) => `${n} ${t}`).join(', ')}
                      </td>
                    </tr>
                  )}
                  {pricePerPen !== undefined && (
                    <tr>
                      <td style={{ padding: '0.25rem 0' }}>Price per pen</td>
                      <td style={{ padding: '0.25rem 0', textAlign: 'right' }}>${pricePerPen}</td>
                    </tr>
                  )}
                  <tr style={{ borderTop: '1px solid #ccc' }}>
                    <td style={{ padding: '0.4rem 0', fontWeight: 'bold' }}>Income</td>
                    <td style={{ padding: '0.4rem 0', textAlign: 'right', fontWeight: 'bold', color: '#2e7d32' }}>
                      ${income.toLocaleString()}
                    </td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <p style={{ color: '#388e3c', fontSize: '0.9rem' }}>
                <strong>No Natural or Improved stock to sell.</strong>
                {haystackPreserved && ' Haystack preserved.'}
              </p>
            )}
            <table style={{ width: '100%', fontSize: '0.9rem', borderCollapse: 'collapse', marginTop: '0.75rem' }}>
              <tbody>
                <tr style={{ borderTop: '1px solid #ccc' }}>
                  <td style={{ padding: '0.4rem 0', color: '#E65100' }}>
                    {extended ? 'Drought extended — clock reset to' : 'Drought clock'}
                  </td>
                  <td style={{ padding: '0.4rem 0', textAlign: 'right', color: '#E65100', fontWeight: 'bold' }}>
                    {droughtSpaces} spaces
                  </td>
                </tr>
              </tbody>
            </table>
          </>
        )}
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
            <button style={btnStyle('#1982c4')} disabled={submitting}
              onClick={() => doAction('decisions/acknowledge')}>OK</button>
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666', marginTop: '0.75rem' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Bore Dries Up — detailed breakdown
  if (pendingAction.action_type === 'bore_dries_up_effect') {
    const notAffected = !data.affected;
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 0.5rem', color: '#d32f2f' }}>Bore Dries Up!</h2>
        {data.space_name && <p style={{ margin: '0 0 0.75rem' }}><strong>{data.space_name}</strong></p>}
        {notAffected ? (
          <p style={{ color: '#388e3c', fontWeight: 'bold' }}>
            {data.reason || 'No effect — you have no Irrigated pasture.'}
          </p>
        ) : (
          <>
            <p style={{ fontSize: '0.85rem', color: '#666', fontStyle: 'italic', margin: '0 0 0.75rem' }}>
              Half of your Irrigated stock (rounded up) is sold to the Bank.
              You cannot restock until the circuit is complete.
            </p>
            <table style={{ width: '100%', fontSize: '0.9rem', borderCollapse: 'collapse' }}>
              <tbody>
                <tr>
                  <td style={{ padding: '0.25rem 0' }}>Irrigated pens sold</td>
                  <td style={{ padding: '0.25rem 0', textAlign: 'right' }}><strong>{data.pens_sold}</strong></td>
                </tr>
                <tr>
                  <td style={{ padding: '0.25rem 0' }}>Price per pen</td>
                  <td style={{ padding: '0.25rem 0', textAlign: 'right' }}>
                    ${data.price_per_pen}{data.had_haystack && <em style={{ color: '#388e3c', marginLeft: 4 }}>(haystack)</em>}
                  </td>
                </tr>
                <tr style={{ borderTop: '1px solid #ccc' }}>
                  <td style={{ padding: '0.4rem 0', fontWeight: 'bold' }}>Income</td>
                  <td style={{ padding: '0.4rem 0', textAlign: 'right', fontWeight: 'bold', color: '#2e7d32' }}>
                    ${(data.income ?? 0).toLocaleString()}
                  </td>
                </tr>
                {data.had_haystack && (
                  <tr>
                    <td style={{ padding: '0.25rem 0', color: '#666' }} colSpan={2}>
                      <em>Haystack consumed (returned to Bank).</em>
                    </td>
                  </tr>
                )}
                <tr style={{ borderTop: '1px solid #ccc' }}>
                  <td style={{ padding: '0.4rem 0', color: '#E65100' }}>Restock blocked for</td>
                  <td style={{ padding: '0.4rem 0', textAlign: 'right', color: '#E65100', fontWeight: 'bold' }}>
                    {data.spaces_blocked} spaces{data.halved_duration && <em style={{ marginLeft: 4 }}>(halved)</em>}
                  </td>
                </tr>
              </tbody>
            </table>
          </>
        )}
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
            <button style={btnStyle('#1982c4')} disabled={submitting}
              onClick={() => doAction('decisions/acknowledge')}>OK</button>
          </div>
        )}
        {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666', marginTop: '0.75rem' }}>Waiting for {activePlayer?.player_name}...</p>}
        {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
      </div>
    );
  }

  // Generic informational actions (drought, flood, etc.)
  const titleMap = {
    drought_effect: 'Local Drought!',
    local_rain: 'Local Rain',
    bore_dries_up_effect: 'Bore Dries Up!',
    flood_effect: 'Flood Damage!',
    stud_ram_dies: 'Stud Ram Dies!',
    visiting_town: 'Visiting Town',
    game_won: 'Game Won!',
    tucker_bag_result: 'Tucker Bag — Card Drawn',
  };

  const title = titleMap[pendingAction.action_type] || pendingAction.action_type;

  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 1rem', color: '#d32f2f' }}>{title}</h2>
      {data.space_name && <p><strong>{data.space_name}</strong></p>}
      {data.no_effect && (
        <p style={{ color: '#388e3c', fontWeight: 'bold' }}>{data.reason || 'No effect.'}</p>
      )}
      {data.total_cost !== undefined && <p>Cost: <strong>${data.total_cost}</strong></p>}
      {data.pens_sold !== undefined && data.pens_sold > 0 && (
        <>
          <p>Pens sold: <strong>{data.pens_sold}</strong>
            {data.no_haystack_price_per_pen && !data.stock_card_used && (
              <span style={{ color: '#666', fontSize: '0.85rem' }}> × ${data.no_haystack_price_per_pen}/pen</span>
            )}
          </p>
          {data.by_type && Object.values(data.by_type).some(n => n > 0) && (
            <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '-0.5rem' }}>
              {Object.entries(data.by_type)
                .filter(([, n]) => n > 0)
                .map(([t, n]) => `${n} ${t}`)
                .join(', ')}
            </p>
          )}
        </>
      )}
      {data.income !== undefined && data.income > 0 && <p>Income: <strong>${data.income}</strong></p>}
      {data.stock_card_used && (
        <div style={{ marginTop: '0.5rem', padding: '0.6rem', background: '#E3F2FD', border: '1px solid #1982c4', borderRadius: 6 }}>
          <strong style={{ color: '#0d47a1' }}>Stock Sale card drawn (haystack)</strong>
          <table style={{ width: '100%', marginTop: 4, fontSize: '0.82rem' }}>
            <tbody>
              {data.stock_card_used.buy_price_per_pen !== undefined && (
                <tr><td>Buy</td><td style={{ textAlign: 'right' }}><strong>${data.stock_card_used.buy_price_per_pen}/pen</strong></td></tr>
              )}
              <tr><td>Sell — Natural</td><td style={{ textAlign: 'right' }}><strong>${data.stock_card_used.sell_price_natural}/pen</strong></td></tr>
              <tr><td>Sell — Improved / Irrigated</td><td style={{ textAlign: 'right' }}><strong>${data.stock_card_used.sell_price_improved_irrigated}/pen</strong></td></tr>
            </tbody>
          </table>
        </div>
      )}
      {data.drought_broken !== undefined && <p>{data.drought_broken ? 'Drought broken!' : 'No drought to break.'}</p>}
      {data.turns_to_miss !== undefined && <p>Miss <strong>{data.turns_to_miss}</strong> turns.</p>}
      {data.total_payment !== undefined && <p>Payment received: <strong>${data.total_payment}</strong></p>}
      {data.winner_name && <p><strong>{data.winner_name}</strong> has won the game!</p>}
      {isMyAction && (
        <button style={{ ...btnStyle('#1982c4'), marginTop: '1rem' }} disabled={submitting}
          onClick={() => doAction('decisions/acknowledge')}>OK</button>
      )}
      {!isMyAction && <p style={{ fontStyle: 'italic', color: '#666' }}>Waiting for {activePlayer?.player_name}...</p>}
      {error && <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>}
    </div>
  );
}
