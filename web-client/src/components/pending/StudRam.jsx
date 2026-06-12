import { useModalChrome } from "./useModalChrome";
import { WaitingFor, ErrorLine, HaystackOffer } from "./shared";

/* Stud Ram spaces: the purchase offer when landing on an unowned ram, and
   the fee receipt when landing on another player's. */
export default function StudRam({ gameId, sessionToken, pendingAction, data, activePlayer, isMyAction, onResolved }) {
  const chrome = useModalChrome({ gameId, sessionToken, onResolved });
  const { modalStyle, btnStyle, submitting, error, doAction } = chrome;

  if (pendingAction.action_type === 'stud_fee_paid') {
    return (
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 1rem', color: '#795548' }}>Stud Fee Paid</h2>
        <p>Paid <strong>${data.amount}</strong> stud fee to <strong>{data.owner_name}</strong> for {data.ram_name}.</p>
        <HaystackOffer data={data} isMyAction={isMyAction} chrome={chrome} />
        {isMyAction && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            <button style={btnStyle('#1982c4')} disabled={submitting} onClick={() => doAction('decisions/acknowledge')}>OK</button>
          </div>
        )}
        <ErrorLine error={error} />
      </div>
    );
  }

  // stud_ram_purchase
  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 1rem', color: '#795548' }}>Stud Ram Available</h2>
      <p><strong>{data.space_name}</strong></p>
      <p>Purchase price: <strong>${data.purchase_price}</strong></p>
      <p>Stud fee earned: <strong>${data.stud_fee}/visit</strong></p>
      <HaystackOffer data={data} isMyAction={isMyAction} chrome={chrome} />
      {isMyAction && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
          <button style={btnStyle('#4caf50')} disabled={submitting} onClick={() => doAction('decisions/stud-ram-buy')}>Buy (${data.purchase_price})</button>
          <button style={btnStyle('#666')} disabled={submitting} onClick={() => doAction('decisions/stud-ram-pass')}>Pass</button>
        </div>
      )}
      {!isMyAction && <WaitingFor activePlayer={activePlayer} />}
      <ErrorLine error={error} />
    </div>
  );
}
