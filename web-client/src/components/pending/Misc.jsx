import { useModalChrome } from "./useModalChrome";
import { WaitingFor, ErrorLine, HaystackOffer } from "./shared";

/* Fire Fighting Equipment offer (before the auction, to the drawer). */
export function FireFightingOffer({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle, btnStyle, submitting, error, doAction } =
    useModalChrome({ gameId, sessionToken, onResolved });
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
      {!isMyAction && <WaitingFor activePlayer={activePlayer} />}
      <ErrorLine error={error} />
    </div>
  );
}

/* Standalone haystack offer (Haymaking landing with no other pending). */
export function HaystackOfferModal({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const chrome = useModalChrome({ gameId, sessionToken, onResolved });
  const { modalStyle, btnStyle, submitting, error, doAction } = chrome;
  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 1rem', color: '#33691E' }}>Haymaking Season</h2>
      <p><strong>{data.space_name}</strong></p>
      <p>You may buy a haystack to protect against drought.</p>
      <HaystackOffer data={data} isMyAction={isMyAction} chrome={chrome} />
      {isMyAction && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
          <button style={btnStyle('#666')} disabled={submitting}
            onClick={() => doAction('decisions/acknowledge')}>Skip</button>
        </div>
      )}
      {!isMyAction && <WaitingFor activePlayer={activePlayer} />}
      <ErrorLine error={error} />
    </div>
  );
}

/* Debt gate: the game is blocked until the debtor raises cash — there is
   no OK button; the pending resolves itself once their balance is >= $0.
   (The debtor's own client suppresses this modal and shows the red debt
   banner with the Emergency Sell / Station buttons instead.) */
export function DebtSettlement({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle } = useModalChrome({ gameId, sessionToken, onResolved });
  const name = data.player_name || activePlayer?.player_name;
  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 1rem', color: '#b71c1c' }}>Debt Must Be Settled</h2>
      <p>
        <strong>{name}</strong> is <strong>${data.debt}</strong> in debt and must
        sell sheep, mortgage paddocks, or sell assets before play can continue.
      </p>
      {isMyAction ? (
        <p style={{ color: '#b71c1c', fontWeight: 'bold' }}>
          Open your Station panel to raise the cash.
        </p>
      ) : (
        <p style={{ fontStyle: 'italic', color: '#666' }}>
          Waiting for {name} to settle the debt...
        </p>
      )}
    </div>
  );
}
