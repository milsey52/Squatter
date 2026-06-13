
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

// "Max's rule": two hazard-keyed haystacks.
const HAYSTACK_LABEL = {
  pasture: 'Pasture haystack (Local Drought)',
  irrigated: 'Irrigated haystack (Bore Dries Up)',
};

/* Haymaking-season rider: pendings carry haystack_offers (a list of the
   useful, not-yet-held haystack types) so the purchase can ride along on
   whatever modal is up. */
export function HaystackOffer({ data, isMyAction, chrome }) {
  const offers = data.haystack_offers || [];
  if (offers.length === 0) return null;
  return (
    <div style={{ marginTop: '0.5rem', padding: '0.6rem', background: '#F1F8E9', border: '1px solid #7CB342', borderRadius: '6px' }}>
      <div>
        <strong style={{ color: '#33691E' }}>Haymaking Season!</strong>
      </div>
      {isMyAction && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
          {offers.map((o) => (
            <button key={o.type} style={chrome.btnStyle('#7CB342')} disabled={chrome.submitting}
              onClick={() => chrome.doAction('station/buy-haystack', { haystack_type: o.type })}>
              Buy {HAYSTACK_LABEL[o.type]} (${o.cost}{o.premium ? ', drought premium' : ''})
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
