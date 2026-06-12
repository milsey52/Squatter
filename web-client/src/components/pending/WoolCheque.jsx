import { useModalChrome } from "./useModalChrome";
import { WaitingFor, ErrorLine } from "./shared";

/* Wool Cheque breakdown — informational popup when landing on or passing
   the Wool Sale (Start) space. */
export default function WoolCheque({ gameId, sessionToken, data, activePlayer, isMyAction, onResolved }) {
  const chrome = useModalChrome({ gameId, sessionToken, onResolved });
  const { modalStyle, btnStyle, submitting, error, doAction } = chrome;

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
      {!isMyAction && <WaitingFor activePlayer={activePlayer} mt="0.75rem" />}
      <ErrorLine error={error} />
    </div>
  );
}
