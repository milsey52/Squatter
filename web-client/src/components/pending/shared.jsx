
export function WaitingFor({ activePlayer, mt }) {
  return (
    <p style={{ fontStyle: 'italic', color: '#666', ...(mt ? { marginTop: mt } : {}) }}>
      Waiting for {activePlayer?.player_name}...
    </p>
  );
}

export function ErrorLine({ error }) {
  if (!error) return null;
  return <p style={{ color: 'red', marginTop: '0.5rem' }}>{error}</p>;
}

/* Haymaking-season rider: many pendings carry haystack_available so the
   purchase can ride along on whatever modal is up. */
export function HaystackOffer({ data, isMyAction, chrome }) {
  if (!data.haystack_available) return null;
  return (
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
        <button style={chrome.btnStyle('#7CB342')} disabled={chrome.submitting}
          onClick={() => chrome.doAction('station/buy-haystack', {})}>
          Buy Haystack (${data.haystack_cost})
        </button>
      )}
    </div>
  );
}
