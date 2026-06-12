import { useModalChrome } from "./useModalChrome";
import { WaitingFor, ErrorLine } from "./shared";

const TITLE_MAP = {
  drought_effect: 'Local Drought!',
  local_rain: 'Local Rain',
  bore_dries_up_effect: 'Bore Dries Up!',
  flood_effect: 'Flood Damage!',
  stud_ram_dies: 'Stud Ram Dies!',
  visiting_town: 'Visiting Town',
  game_won: 'Game Won!',
  tucker_bag_result: 'Tucker Bag — Card Drawn',
};

/* Catch-all informational popup: renders whichever well-known fields the
   pending's data carries, with a plain OK acknowledge. */
export default function GenericInfo({ gameId, sessionToken, pendingAction, data, activePlayer, isMyAction, onResolved }) {
  const chrome = useModalChrome({ gameId, sessionToken, onResolved });
  const { modalStyle, btnStyle, submitting, error, doAction } = chrome;

  const title = TITLE_MAP[pendingAction.action_type] || pendingAction.action_type;

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
      {!isMyAction && <WaitingFor activePlayer={activePlayer} />}
      <ErrorLine error={error} />
    </div>
  );
}
