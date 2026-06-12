import { useState } from "react";
import { useModalChrome } from "./useModalChrome";
import { WaitingFor, ErrorLine, HaystackOffer } from "./shared";

/* Stock Sale — DECLARE step. Per the rules the player commits to buy/sell
   and the number of pens BEFORE the Stock Sale card is revealed; once a
   buy is committed the price is locked and retries may only reduce. */
export default function StockSaleDecision({
  gameId, sessionToken, data, activePlayer, isMyAction, onResolved,
  activePlayerHasHighStockPrices,
}) {
  const chrome = useModalChrome({ gameId, sessionToken, onResolved });
  const { modalStyle, btnStyle, submitting, error, setError, doAction } = chrome;
  const [pens, setPens] = useState(1);
  const [useHighStockPrices, setUseHighStockPrices] = useState(false);
  // Two-step flow: null = choose action, 'buy'|'sell' = enter pens
  const [stockSaleAction, setStockSaleAction] = useState(null);
  // Opt-in to consume the pending next-sell-price auto modifier
  const [useAutoSellModifier, setUseAutoSellModifier] = useState(true);
  // Sell step: per-tier pen allocation
  const [sellNatural, setSellNatural] = useState(0);
  const [sellImproved, setSellImproved] = useState(0);
  const [sellIrrigated, setSellIrrigated] = useState(0);

  const buyCommitted = !!data.buy_committed;
  const originalPens = data.original_pens ?? 0;
  const hspLocked = !!data.hsp_locked;
  // Restock block can be scoped: 'all' bars all buying, 'irrigated' bars
  // only Irrigated paddocks (Natural/Improved buying still allowed).
  const blockScope = data.restock_blocked ? (data.restock_block_scope || 'all') : null;
  const buyAllowed = blockScope !== 'all';
  // Available buy capacity depends on the combination of block scope + drought.
  const nonIrrigatedEmpty = (data.empty_natural_pens ?? 0) + (data.empty_improved_pens ?? 0);
  const allEmpty = data.empty_pens ?? 0;
  let buyPool = allEmpty;
  if (blockScope === 'irrigated' && !data.in_drought) {
    buyPool = nonIrrigatedEmpty;
  } else if (data.in_drought) {
    buyPool = data.empty_irrigated_pens ?? 0;
  }
  const maxBuy = buyCommitted
    ? Math.min(originalPens, buyPool, data.max_per_transaction ?? 15)
    : Math.min(buyPool, data.max_per_transaction ?? 15);
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
          <strong>Restock blocked
            {blockScope === 'irrigated' && ' (Irrigated only)'}.
          </strong>{' '}
          {blockScope === 'irrigated' ? (
            <>You cannot buy stock into Irrigated paddocks until the circuit is complete{data.restock_block_spaces_remaining > 0 && <> ({data.restock_block_spaces_remaining} spaces remaining)</>}. Natural/Improved restocking is still allowed.</>
          ) : (
            <>You cannot buy stock until the circuit is complete{data.restock_block_spaces_remaining > 0 && <> ({data.restock_block_spaces_remaining} spaces remaining)</>}. Selling and passing are still allowed.</>
          )}
        </div>
      )}
      {/* Modifiers / status summary */}
      <div style={{ marginTop: '0.5rem', padding: '0.6rem', background: '#F1F8E9', border: '1px solid #c5e1a5', borderRadius: '6px', fontSize: '0.85rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span><strong>Your balance:</strong></span>
          <span><strong>${(data.balance ?? 0).toLocaleString()}</strong></span>
        </div>
        <div style={{ fontWeight: 'bold', marginBottom: 4, fontSize: '0.82rem', color: '#33691E' }}>Active modifiers</div>
        <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.82rem' }}>
          {data.next_sell_price_modifier > 0 && (
            <li>+{data.next_sell_price_modifier}% sell bonus pending (from Worm Control Programme / Control of Weeds / Fertilised Pasture)</li>
          )}
          {activePlayerHasHighStockPrices && (
            <li>High Stock Prices card available (+20% to buy or sell — opt-in below; discards card)</li>
          )}
          {data.in_drought && (
            <li>Drought: Natural/Improved sell at half price; Irrigated unaffected</li>
          )}
          {!(data.next_sell_price_modifier > 0) && !activePlayerHasHighStockPrices && !data.in_drought && (
            <li style={{ color: '#666' }}>No active modifiers — stock sale uses card prices as-is.</li>
          )}
        </ul>
      </div>
      <HaystackOffer data={data} isMyAction={isMyAction} chrome={chrome} />
      {isMyAction && buyCommitted && (
        // Locked retry: only allow Buy (fewer pens) or Pass
        <>
          {activePlayerHasHighStockPrices && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.5rem', padding: '0.5rem', background: '#FFF8E1', border: '1px solid #FFB300', borderRadius: '6px', opacity: 0.7 }}>
              <input type="checkbox" checked={hspLocked} disabled
                onChange={(e) => setUseHighStockPrices(e.target.checked)} />
              <span style={{ fontSize: '0.9rem' }}>
                Apply <strong>High Stock Prices</strong> (+20% — locked)
              </span>
            </label>
          )}
          <div style={{ marginTop: '1rem' }}>
            <label>Pens: <input type="number" min={1} max={maxBuy} value={pens} onChange={e => setPens(Number(e.target.value))} style={{ width: 60, marginLeft: 8 }} /></label>
            <span style={{ marginLeft: 12, fontSize: '0.78rem', color: '#666' }}>max buy {maxBuy}</span>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
              <button style={btnStyle('#4caf50')} disabled={submitting || pens > maxBuy || pens < 1}
                onClick={() => doAction('decisions/stock-sale', { action: 'buy', pens, use_high_stock_prices: useHighStockPrices })}>Buy {pens}</button>
              <button style={btnStyle('#666')} disabled={submitting} onClick={() => doAction('decisions/stock-sale', { action: 'pass' })}>Pass</button>
            </div>
          </div>
        </>
      )}
      {isMyAction && !buyCommitted && stockSaleAction === null && (
        // Step 1: pick Buy / Sell / Pass
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
          <button style={btnStyle('#4caf50')} disabled={submitting || maxBuy < 1 || !buyAllowed}
            title={!buyAllowed ? 'Restock blocked — complete the circuit first' :
                   (blockScope === 'irrigated' ? 'Bore Dries Up: Natural/Improved only' : undefined)}
            onClick={() => { setError(null); setStockSaleAction('buy'); setPens(1); }}>Buy</button>
          <button style={btnStyle('#ff9800')} disabled={submitting || maxSell < 1}
            onClick={() => { setError(null); setStockSaleAction('sell'); setPens(1); }}>Sell</button>
          <button style={btnStyle('#666')} disabled={submitting}
            onClick={() => doAction('decisions/stock-sale', { action: 'pass' })}>Pass</button>
        </div>
      )}
      {isMyAction && !buyCommitted && stockSaleAction !== null && (
        // Step 2: enter pens for the chosen action
        <>
          {activePlayerHasHighStockPrices && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.5rem', padding: '0.5rem', background: '#FFF8E1', border: '1px solid #FFB300', borderRadius: '6px' }}>
              <input type="checkbox" checked={useHighStockPrices}
                onChange={(e) => setUseHighStockPrices(e.target.checked)} />
              <span style={{ fontSize: '0.9rem' }}>
                Apply <strong>High Stock Prices</strong> (+20% to {stockSaleAction} — discards card)
              </span>
            </label>
          )}
          {stockSaleAction === 'sell' && data.next_sell_price_modifier > 0 && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.5rem', padding: '0.5rem', background: '#E8F5E9', border: '1px solid #66BB6A', borderRadius: '6px' }}>
              <input type="checkbox" checked={useAutoSellModifier}
                onChange={(e) => setUseAutoSellModifier(e.target.checked)} />
              <span style={{ fontSize: '0.9rem' }}>
                Apply <strong>+{data.next_sell_price_modifier}%</strong> sell bonus this sale
                <em style={{ marginLeft: 4, color: '#666', fontSize: '0.78rem' }}>
                  (uncheck to save for a later sale)
                </em>
              </span>
            </label>
          )}
          {stockSaleAction === 'buy' ? (
            <div style={{ marginTop: '1rem' }}>
              <label>Pens to buy: <input type="number" min={1} max={maxBuy}
                value={pens} onChange={e => setPens(Number(e.target.value))}
                style={{ width: 60, marginLeft: 8 }} /></label>
              <span style={{ marginLeft: 12, fontSize: '0.78rem', color: '#666' }}>
                max {maxBuy}
              </span>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
                <button style={btnStyle('#4caf50')}
                  disabled={submitting || pens < 1 || pens > maxBuy}
                  onClick={() => doAction('decisions/stock-sale', { action: 'buy', pens, use_high_stock_prices: useHighStockPrices, use_auto_sell_modifier: useAutoSellModifier })}>
                  Confirm Buy {pens}
                </button>
                <button style={btnStyle('#666')} disabled={submitting}
                  onClick={() => { setError(null); setStockSaleAction(null); setUseHighStockPrices(false); setUseAutoSellModifier(true); }}>Back</button>
              </div>
            </div>
          ) : (() => {
            const heldNat = data.natural_pens ?? 0;
            const heldImp = data.improved_pens ?? 0;
            const heldIrr = data.irrigated_pens ?? 0;
            const totalSell = sellNatural + sellImproved + sellIrrigated;
            const maxPerTxn = data.max_per_transaction ?? 15;
            const overTier =
              sellNatural > heldNat || sellImproved > heldImp || sellIrrigated > heldIrr;
            const overTotal = totalSell > maxPerTxn;
            const disabled = submitting || totalSell < 1 || overTier || overTotal;
            const tierRow = (label, value, setValue, held, color) => (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: 4 }}>
                <span style={{ minWidth: 110, fontSize: '0.88rem', color }}>{label}</span>
                <input type="number" min={0} max={held}
                  value={value} onChange={e => setValue(Math.max(0, Number(e.target.value)))}
                  disabled={held === 0}
                  style={{ width: 60 }} />
                <span style={{ fontSize: '0.78rem', color: '#666' }}>of {held}</span>
              </div>
            );
            return (
              <div style={{ marginTop: '1rem' }}>
                <p style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: '#555' }}>
                  Choose how many pens to sell from each pasture type:
                </p>
                {tierRow('Natural', sellNatural, setSellNatural, heldNat, '#8d6e63')}
                {tierRow('Improved', sellImproved, setSellImproved, heldImp, '#66bb6a')}
                {tierRow('Irrigated', sellIrrigated, setSellIrrigated, heldIrr, '#42a5f5')}
                <p style={{ margin: '0.5rem 0', fontSize: '0.85rem' }}>
                  Total to sell: <strong>{totalSell}</strong> pens
                  <span style={{ marginLeft: 8, color: '#666', fontSize: '0.78rem' }}>
                    (max {maxPerTxn} per transaction)
                  </span>
                </p>
                {overTier && <p style={{ color: '#b71c1c', fontSize: '0.82rem', margin: 0 }}>
                  A tier exceeds what you own.
                </p>}
                {overTotal && <p style={{ color: '#b71c1c', fontSize: '0.82rem', margin: 0 }}>
                  Total exceeds the {maxPerTxn}-pen per-transaction limit.
                </p>}
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                  <button style={btnStyle('#ff9800')} disabled={disabled}
                    onClick={() => doAction('decisions/stock-sale', {
                      action: 'sell',
                      pens_by_type: {
                        natural: sellNatural,
                        improved: sellImproved,
                        irrigated: sellIrrigated,
                      },
                      use_high_stock_prices: useHighStockPrices,
                      use_auto_sell_modifier: useAutoSellModifier,
                    })}>
                    Confirm Sell {totalSell}
                  </button>
                  <button style={btnStyle('#666')} disabled={submitting}
                    onClick={() => {
                      setError(null); setStockSaleAction(null);
                      setUseHighStockPrices(false); setUseAutoSellModifier(true);
                      setSellNatural(0); setSellImproved(0); setSellIrrigated(0);
                    }}>Back</button>
                </div>
              </div>
            );
          })()}
        </>
      )}
      {!isMyAction && <WaitingFor activePlayer={activePlayer} />}
      <ErrorLine error={error} />
    </div>
  );
}
