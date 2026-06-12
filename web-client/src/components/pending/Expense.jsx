import { useModalChrome } from "./useModalChrome";
import { WaitingFor, ErrorLine, HaystackOffer } from "./shared";

/* Expense spaces: the standard pay-and-acknowledge, and the Drench Sheep
   for Worms space with two mutually-exclusive payment options. */
export default function Expense({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const chrome = useModalChrome({ gameId, sessionToken, onResolved });
  const { modalStyle, btnStyle, submitting, error, doAction } = chrome;

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
        <HaystackOffer data={data} isMyAction={isMyAction} chrome={chrome} />
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
          </div>
        )}
        {!isMyAction && <WaitingFor activePlayer={activePlayer} />}
        <ErrorLine error={error} />
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
      {data.blowfly_cleared_pct && (
        <p style={{ color: '#4caf50', fontWeight: 'bold', marginTop: '0.5rem' }}>
          Blowfly Wave penalty cleared (−{data.blowfly_cleared_pct}% wool cheque reduction lifted).
        </p>
      )}
      <HaystackOffer data={data} isMyAction={isMyAction} chrome={chrome} />
      {isMyAction && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
          <button style={btnStyle('#1982c4')} disabled={submitting}
            onClick={() => doAction('decisions/expense', { buy_card: false })}>OK</button>
        </div>
      )}
      {!isMyAction && <WaitingFor activePlayer={activePlayer} />}
      <ErrorLine error={error} />
    </div>
  );
}
