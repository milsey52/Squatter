import { useModalChrome } from "./useModalChrome";
import { WaitingFor, ErrorLine } from "./shared";

/* Drought-family popups: Local Drought breakdown, Bore Dries Up breakdown,
   and the Drought on ALL Stations per-player summary table. */
export default function DroughtEffects(props) {
  const t = props.pendingAction.action_type;
  if (t === 'bore_dries_up_effect') return <BoreDriesUp {...props} />;
  if (t === 'drought_all_stations_result') return <DroughtAllStations {...props} />;
  return <LocalDrought {...props} />;
}

function LocalDrought({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle, btnStyle, submitting, error, doAction } =
    useModalChrome({ gameId, sessionToken, onResolved });

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
      {!isMyAction && <WaitingFor activePlayer={activePlayer} mt="0.75rem" />}
      <ErrorLine error={error} />
    </div>
  );
}

function BoreDriesUp({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle, btnStyle, submitting, error, doAction } =
    useModalChrome({ gameId, sessionToken, onResolved });
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
      {!isMyAction && <WaitingFor activePlayer={activePlayer} mt="0.75rem" />}
      <ErrorLine error={error} />
    </div>
  );
}

function DroughtAllStations({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const { modalStyle, btnStyle, submitting, error, doAction } =
    useModalChrome({ gameId, sessionToken, onResolved });
  const breakdowns = data.breakdowns || [];
  const labelFor = (b) => {
    if (b.outcome === 'no_effect') return 'No effect';
    if (b.outcome === 'extended') return 'Already in drought';
    return b.had_haystack && b.stock_card_used ? 'Affected · haystack' : 'Affected';
  };
  return (
    <div style={{ ...modalStyle, minWidth: 520, maxWidth: 640 }}>
      <h2 style={{ margin: '0 0 0.5rem', color: '#d32f2f' }}>
        {data.card_title || 'Drought on ALL Stations'}
      </h2>
      <p style={{ fontSize: '0.9rem', color: '#555', margin: '0 0 0.5rem' }}>
        Drought applied to every active station.
      </p>
      <p style={{ fontSize: '0.82rem', color: '#666', fontStyle: 'italic', margin: '0 0 0.75rem' }}>
        Each affected player sells half their Natural/Improved stock at
        ${data.no_haystack_price_per_pen ?? 500}/pen (or Stock Sale prices if a
        Haystack offsets — haystack consumed). Drought clock: 44 spaces.
      </p>
      <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #999', fontSize: '0.78rem', color: '#555' }}>
            <th style={{ textAlign: 'left', padding: '0.3rem 0.4rem' }}>Player</th>
            <th style={{ textAlign: 'left', padding: '0.3rem 0.4rem' }}>Outcome</th>
            <th style={{ textAlign: 'right', padding: '0.3rem 0.4rem' }}>Sold</th>
            <th style={{ textAlign: 'right', padding: '0.3rem 0.4rem' }}>Income</th>
            <th style={{ textAlign: 'right', padding: '0.3rem 0.4rem' }}>Clock</th>
          </tr>
        </thead>
        <tbody>
          {breakdowns.map((b) => {
            const tiers = b.by_type
              ? Object.entries(b.by_type).filter(([, n]) => n > 0).map(([t, n]) => `${n} ${t}`).join(', ')
              : '';
            return (
              <tr key={b.player_id} style={{ borderBottom: '1px solid #eee', verticalAlign: 'top' }}>
                <td style={{ padding: '0.4rem' }}><strong>{b.player_name}</strong></td>
                <td style={{ padding: '0.4rem', color: b.outcome === 'no_effect' ? '#388e3c' : '#b71c1c' }}>
                  {labelFor(b)}
                  {b.outcome === 'no_effect' && (
                    <div style={{ fontSize: '0.72rem', color: '#666', fontStyle: 'italic' }}>
                      all Irrigated
                    </div>
                  )}
                  {b.outcome === 'extended' && (
                    <div style={{ fontSize: '0.72rem', color: '#666', fontStyle: 'italic' }}>
                      clock reset
                    </div>
                  )}
                  {b.had_haystack && b.stock_card_used && b.outcome === 'affected' && (
                    <div style={{ fontSize: '0.72rem', color: '#666', fontStyle: 'italic' }}>
                      haystack consumed
                    </div>
                  )}
                </td>
                <td style={{ padding: '0.4rem', textAlign: 'right' }}>
                  {b.pens_sold > 0 ? <><strong>{b.pens_sold}</strong> pens</> : '—'}
                  {tiers && <div style={{ fontSize: '0.72rem', color: '#666' }}>{tiers}</div>}
                </td>
                <td style={{ padding: '0.4rem', textAlign: 'right', color: b.income > 0 ? '#2e7d32' : '#888' }}>
                  {b.income > 0 ? `$${b.income.toLocaleString()}` : '—'}
                </td>
                <td style={{ padding: '0.4rem', textAlign: 'right' }}>
                  {b.drought_spaces > 0 ? b.drought_spaces : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
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
