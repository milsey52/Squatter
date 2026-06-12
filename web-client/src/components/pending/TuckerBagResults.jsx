import { useModalChrome } from "./useModalChrome";
import { WaitingFor, ErrorLine } from "./shared";
import GenericInfo from "./GenericInfo";

/* tucker_bag_result reconciliation popups, per effect code. Effects whose
   data carries stock_card_used are board-anchored overlays (suppressed by
   the dispatcher); anything unrecognized falls back to GenericInfo. */
export default function TuckerBagResult(props) {
  const { data } = props;
  if (data.effect_code === 'FIRE_DAMAGE') return <FireDamage {...props} />;
  if (data.effect_code === 'WORM_INFESTATION') return <WormInfestation {...props} />;
  if (data.effect_code === 'BLOWFLY_WAVE') return <BlowflyWave {...props} />;
  if (data.effect_code === 'GRASS_FIRE' && data.protected) return <GrassFireProtected {...props} />;
  if (data.effect_code === 'LUCERNE_FLEA') return <LucerneFlea {...props} />;
  return <GenericInfo {...props} />;
}

function FireDamage({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle, btnStyle, submitting, error, doAction } =
    useModalChrome({ gameId, sessionToken, onResolved });
  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 0.5rem', color: '#d32f2f' }}>
        {data.card_title || 'Fire Destroys Haystack'}
      </h2>
      {data.protected ? (
        <p style={{ color: '#388e3c', fontWeight: 'bold', fontSize: '1rem' }}>
          No loss — <em>{data.protection_card || 'Fire Fighting Equipment'}</em> card held.
        </p>
      ) : (
        <>
          <p style={{ fontSize: '0.9rem', color: '#555', margin: '0 0 0.5rem' }}>
            No <em>{data.protection_card || 'Fire Fighting Equipment'}</em> card held.
          </p>
          <table style={{ width: '100%', fontSize: '0.9rem', borderCollapse: 'collapse' }}>
            <tbody>
              <tr>
                <td style={{ padding: '0.25rem 0' }}>Repair cost</td>
                <td style={{ padding: '0.25rem 0', textAlign: 'right', fontWeight: 'bold', color: '#b71c1c' }}>
                  −${(data.cost ?? 0).toLocaleString()}
                </td>
              </tr>
              {data.haystack_lost ? (
                <tr>
                  <td style={{ padding: '0.25rem 0', color: '#666' }} colSpan={2}>
                    Haystack lost (returned to Bank).
                  </td>
                </tr>
              ) : (
                <tr>
                  <td style={{ padding: '0.25rem 0', color: '#666', fontStyle: 'italic' }} colSpan={2}>
                    (No haystack to lose.)
                  </td>
                </tr>
              )}
              <tr style={{ borderTop: '1px solid #ccc' }}>
                <td style={{ padding: '0.4rem 0', fontWeight: 'bold' }}>Total cost</td>
                <td style={{ padding: '0.4rem 0', textAlign: 'right', fontWeight: 'bold', color: '#b71c1c' }}>
                  ${(data.cost ?? 0).toLocaleString()}
                </td>
              </tr>
            </tbody>
          </table>
        </>
      )}
      {isMyAction && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
          <button style={btnStyle('#d32f2f')} disabled={submitting}
            onClick={() => doAction('decisions/acknowledge')}>OK</button>
        </div>
      )}
      {!isMyAction && <WaitingFor activePlayer={activePlayer} mt="0.75rem" />}
      <ErrorLine error={error} />
    </div>
  );
}

function WormInfestation({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle, btnStyle, submitting, error, doAction } =
    useModalChrome({ gameId, sessionToken, onResolved });
  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 0.5rem', color: '#6a4c93' }}>
        {data.card_title || 'Worm Infestation'}
      </h2>
      {data.protected ? (
        <p style={{ color: '#388e3c', fontWeight: 'bold', fontSize: '1rem' }}>
          No loss — <em>{data.protection_card || 'Worm Control Program'}</em> card held.
        </p>
      ) : (
        <>
          <p style={{ fontSize: '0.9rem', color: '#555', margin: '0 0 0.5rem' }}>
            No <em>{data.protection_card || 'Worm Control Program'}</em> card held.
            Sell {data.fraction_text || '1/2'} of stock at ${data.sell_price_per_pen}/pen.
          </p>
          <table style={{ width: '100%', fontSize: '0.9rem', borderCollapse: 'collapse' }}>
            <tbody>
              <tr>
                <td style={{ padding: '0.25rem 0' }}>
                  {data.total_pens_before} pens × {data.fraction_text || '1/2'}
                </td>
                <td style={{ padding: '0.25rem 0', textAlign: 'right' }}>
                  <strong>{data.pens_sold}</strong> pens
                </td>
              </tr>
              {data.by_type && Object.values(data.by_type).some(n => n > 0) && (
                <tr>
                  <td style={{ padding: '0 0 0.25rem 0', fontSize: '0.78rem', color: '#666' }} colSpan={2}>
                    {Object.entries(data.by_type).filter(([, n]) => n > 0).map(([t, n]) => `${n} ${t}`).join(', ')}
                  </td>
                </tr>
              )}
              <tr>
                <td style={{ padding: '0.25rem 0' }}>
                  {data.pens_sold} pens × ${data.sell_price_per_pen}/pen
                </td>
                <td style={{ padding: '0.25rem 0', textAlign: 'right', fontWeight: 'bold', color: '#2e7d32' }}>
                  ${(data.income ?? 0).toLocaleString()}
                </td>
              </tr>
              <tr style={{ borderTop: '1px solid #ccc' }}>
                <td style={{ padding: '0.4rem 0', color: '#E65100', fontWeight: 'bold' }} colSpan={2}>
                  Restock blocked until you land on the next Stock Sale.
                </td>
              </tr>
            </tbody>
          </table>
        </>
      )}
      {isMyAction && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
          <button style={btnStyle('#6a4c93')} disabled={submitting}
            onClick={() => doAction('decisions/acknowledge')}>OK</button>
        </div>
      )}
      {!isMyAction && <WaitingFor activePlayer={activePlayer} mt="0.75rem" />}
      <ErrorLine error={error} />
    </div>
  );
}

function BlowflyWave({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle, btnStyle, submitting, error, doAction } =
    useModalChrome({ gameId, sessionToken, onResolved });
  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 0.5rem', color: '#d32f2f' }}>
        {data.card_title || 'Blowfly Wave'}
      </h2>
      <p style={{ fontSize: '0.95rem', color: '#555' }}>
        Your next Wool Cheque will reduce by <strong>{data.wool_reduction_pct ?? 10}%</strong>.
      </p>
      <p style={{ fontSize: '0.85rem', color: '#666', fontStyle: 'italic', marginTop: '0.5rem' }}>
        No loss if you land on Jet Sheep / Fly Strike Dip before your next Wool Cheque.
      </p>
      {isMyAction && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
          <button style={btnStyle('#d32f2f')} disabled={submitting}
            onClick={() => doAction('decisions/acknowledge')}>OK</button>
        </div>
      )}
      {!isMyAction && <WaitingFor activePlayer={activePlayer} mt="0.75rem" />}
      <ErrorLine error={error} />
    </div>
  );
}

/* Grass Fire — PROTECTED case only. The unprotected case has
   stock_card_used set and renders as the board-anchored overlay. */
function GrassFireProtected({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle, btnStyle, submitting, error, doAction } =
    useModalChrome({ gameId, sessionToken, onResolved });
  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 0.5rem', color: '#d32f2f' }}>
        {data.card_title || 'Grass Fire'}
      </h2>
      <p style={{ color: '#388e3c', fontWeight: 'bold', fontSize: '1rem' }}>
        No loss — <em>{data.protection_card || 'Fire Fighting Equipment'}</em> card held.
      </p>
      {isMyAction && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
          <button style={btnStyle('#d32f2f')} disabled={submitting}
            onClick={() => doAction('decisions/acknowledge')}>OK</button>
        </div>
      )}
      {!isMyAction && <WaitingFor activePlayer={activePlayer} mt="0.75rem" />}
      <ErrorLine error={error} />
    </div>
  );
}

function LucerneFlea({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle, btnStyle, submitting, error, doAction } =
    useModalChrome({ gameId, sessionToken, onResolved });
  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 0.5rem', color: '#6a4c93' }}>
        {data.card_title || 'Lucerne Flea Infestation'}
      </h2>
      {data.protected ? (
        <p style={{ color: '#388e3c', fontWeight: 'bold', fontSize: '1rem' }}>
          No loss — <em>{data.protection_card || 'Control of Weeds and Insects'}</em> card held.
        </p>
      ) : (
        <>
          <p style={{ fontSize: '0.9rem', color: '#555', margin: '0 0 0.5rem' }}>
            No <em>{data.protection_card || 'Control of Weeds and Insects'}</em> card held.
            Sell {data.fraction_text || '1/3'} of stock at ${data.sell_price_per_pen}/pen.
          </p>
          <table style={{ width: '100%', fontSize: '0.9rem', borderCollapse: 'collapse' }}>
            <tbody>
              <tr>
                <td style={{ padding: '0.25rem 0' }}>
                  {data.total_pens_before} pens × {data.fraction_text || '1/3'}
                </td>
                <td style={{ padding: '0.25rem 0', textAlign: 'right' }}>
                  <strong>{data.pens_sold}</strong> pens
                </td>
              </tr>
              {data.by_type && Object.values(data.by_type).some(n => n > 0) && (
                <tr>
                  <td style={{ padding: '0 0 0.25rem 0', fontSize: '0.78rem', color: '#666' }} colSpan={2}>
                    {Object.entries(data.by_type).filter(([, n]) => n > 0).map(([t, n]) => `${n} ${t}`).join(', ')}
                  </td>
                </tr>
              )}
              <tr>
                <td style={{ padding: '0.25rem 0' }}>
                  {data.pens_sold} pens × ${data.sell_price_per_pen}/pen
                </td>
                <td style={{ padding: '0.25rem 0', textAlign: 'right', fontWeight: 'bold', color: '#2e7d32' }}>
                  ${(data.income ?? 0).toLocaleString()}
                </td>
              </tr>
              {data.restock_blocked && (
                <tr style={{ borderTop: '1px solid #ccc' }}>
                  <td style={{ padding: '0.4rem 0', color: '#E65100' }} colSpan={2}>
                    Restock blocked until full circuit.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}
      {isMyAction && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
          <button style={btnStyle('#6a4c93')} disabled={submitting}
            onClick={() => doAction('decisions/acknowledge')}>OK</button>
        </div>
      )}
      {!isMyAction && <WaitingFor activePlayer={activePlayer} mt="0.75rem" />}
      <ErrorLine error={error} />
    </div>
  );
}
