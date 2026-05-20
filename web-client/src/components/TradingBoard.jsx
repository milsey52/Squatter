import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function TradingBoard({ gameId, sessionToken, userId, game, playerBalances, playerRetainedCards, activeTradeFromParent, onClose }) {
  const [activeTrade, setActiveTrade] = useState(activeTradeFromParent);
  const [selectedCounterparty, setSelectedCounterparty] = useState(null);
  const [isInitiating, setIsInitiating] = useState(false);
  const [error, setError] = useState(null);

  // Initiator's offer
  const [initiatorCash, setInitiatorCash] = useState(0);
  const [initiatorStudRamIds, setInitiatorStudRamIds] = useState([]);

  // Counterparty's offer
  const [counterpartyCash, setCounterpartyCash] = useState(0);
  const [counterpartyStudRamIds, setCounterpartyStudRamIds] = useState([]);

  // Stud ram data
  const [studRams, setStudRams] = useState([]);

  const currentUserPlayer = game.players?.find(p => p.user_id === userId);

  const [lastTradeSessionId, setLastTradeSessionId] = useState(null);

  const isUserInitiator = currentUserPlayer && activeTradeFromParent?.initiator_player_id === currentUserPlayer.game_player_id;
  const isUserCounterparty = currentUserPlayer && activeTradeFromParent?.counterparty_player_id === currentUserPlayer.game_player_id;

  // Fetch stud rams
  useEffect(() => {
    fetch(`${API_BASE}/games/${gameId}/stud-rams`, {
      headers: { 'Authorization': `Bearer ${sessionToken}` }
    })
      .then(res => res.ok ? res.json() : [])
      .then(data => setStudRams(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, [gameId, sessionToken]);

  // Sync with parent's active trade
  useEffect(() => {
    setActiveTrade(activeTradeFromParent);

    const newTradeSessionId = activeTradeFromParent?.trade_session_id;

    if (activeTradeFromParent && newTradeSessionId !== lastTradeSessionId) {
      setLastTradeSessionId(newTradeSessionId);

      if (activeTradeFromParent.initiator_offer) {
        setInitiatorCash(activeTradeFromParent.initiator_offer.cash || 0);
        setInitiatorStudRamIds(activeTradeFromParent.initiator_offer.stud_ram_space_ids || []);
      }
      if (activeTradeFromParent.counterparty_offer) {
        setCounterpartyCash(activeTradeFromParent.counterparty_offer.cash || 0);
        setCounterpartyStudRamIds(activeTradeFromParent.counterparty_offer.stud_ram_space_ids || []);
      }
    } else if (!activeTradeFromParent) {
      setLastTradeSessionId(null);
    }
  }, [activeTradeFromParent, lastTradeSessionId]);

  // Sync other party's offer
  useEffect(() => {
    if (!activeTradeFromParent || !lastTradeSessionId) return;

    if (isUserInitiator && activeTradeFromParent.counterparty_offer) {
      setCounterpartyCash(activeTradeFromParent.counterparty_offer.cash || 0);
      setCounterpartyStudRamIds(activeTradeFromParent.counterparty_offer.stud_ram_space_ids || []);
    }
    if (isUserCounterparty && activeTradeFromParent.initiator_offer) {
      setInitiatorCash(activeTradeFromParent.initiator_offer.cash || 0);
      setInitiatorStudRamIds(activeTradeFromParent.initiator_offer.stud_ram_space_ids || []);
    }
  }, [
    activeTradeFromParent?.initiator_offer,
    activeTradeFromParent?.counterparty_offer,
    isUserInitiator,
    isUserCounterparty,
    lastTradeSessionId
  ]);

  const initiateTrade = async () => {
    if (!selectedCounterparty) {
      setError('Please select a trading partner');
      return;
    }

    setIsInitiating(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/trades/initiate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionToken}`
        },
        body: JSON.stringify({
          counterparty_player_id: parseInt(selectedCounterparty)
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to initiate trade');
      }

      const data = await response.json();
      setActiveTrade({
        trade_session_id: data.trade_session_id,
        game_id: gameId,
        initiator_player_id: data.initiator_player_id,
        counterparty_player_id: data.counterparty_player_id,
        status: data.status,
        initiator_offer: { cash: 0, stud_ram_space_ids: [] },
        counterparty_offer: { cash: 0, stud_ram_space_ids: [] },
      });

      setInitiatorCash(0);
      setInitiatorStudRamIds([]);
      setCounterpartyCash(0);
      setCounterpartyStudRamIds([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsInitiating(false);
    }
  };

  const updateOffer = async (isInitiator) => {
    if (!activeTrade) return;

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/trades/${activeTrade.trade_session_id}/update-offer`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionToken}`
        },
        body: JSON.stringify({
          cash: isInitiator ? initiatorCash : counterpartyCash,
          stud_ram_space_ids: isInitiator ? initiatorStudRamIds : counterpartyStudRamIds
        })
      });

      if (!response.ok) throw new Error('Failed to update offer');
    } catch (err) {
      setError(err.message);
    }
  };

  const acceptInvite = async (accept) => {
    if (!activeTrade) return;

    try {
      const response = await fetch(
        `${API_BASE}/games/${gameId}/trades/${activeTrade.trade_session_id}/accept-invite?accept=${accept}`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${sessionToken}` }
        }
      );

      if (!response.ok) throw new Error('Failed to respond to invite');
      if (!accept) onClose();
    } catch (err) {
      setError(err.message);
    }
  };

  const cancelTrade = async () => {
    if (!activeTrade) return;

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/trades/${activeTrade.trade_session_id}/cancel`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${sessionToken}` }
      });

      if (!response.ok) throw new Error('Failed to cancel trade');
      setActiveTrade(null);
      setSelectedCounterparty(null);
    } catch (err) {
      setError(err.message);
    }
  };

  const acceptTrade = async () => {
    if (!activeTrade) return;

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/trades/${activeTrade.trade_session_id}/accept`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${sessionToken}` }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to accept trade');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const executeTrade = async () => {
    if (!activeTrade) return;

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/trades/${activeTrade.trade_session_id}/execute`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${sessionToken}` }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to execute trade');
      }

      setActiveTrade(null);
      setSelectedCounterparty(null);
      onClose();
    } catch (err) {
      setError(err.message);
    }
  };

  const isInitiator = activeTrade && currentUserPlayer && activeTrade.initiator_player_id === currentUserPlayer.game_player_id;
  const isCounterparty = activeTrade && currentUserPlayer && activeTrade.counterparty_player_id === currentUserPlayer.game_player_id;

  const initiatorPlayer = activeTrade ? game.players.find(p => p.game_player_id === activeTrade.initiator_player_id) : currentUserPlayer;
  const counterpartyPlayer = activeTrade && activeTrade.counterparty_player_id ?
    game.players.find(p => p.game_player_id === activeTrade.counterparty_player_id) : null;

  const initiatorBalance = initiatorPlayer ? (playerBalances[String(initiatorPlayer.game_player_id)] ?? 0) : 0;
  const counterpartyBalance = counterpartyPlayer ? (playerBalances[String(counterpartyPlayer.game_player_id)] ?? 0) : 0;

  // Get stud rams owned by each player
  const initiatorRams = studRams.filter(r => r.owner_game_player_id === initiatorPlayer?.game_player_id);
  const counterpartyRams = studRams.filter(r => r.owner_game_player_id === counterpartyPlayer?.game_player_id);

  // Counterparty selection screen
  if (!activeTrade) {
    const otherPlayers = game.players.filter(p => p.game_player_id !== currentUserPlayer?.game_player_id);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
        <div style={{ flex: 1, padding: '1rem' }}>
          <h3 style={{ marginTop: 0 }}>Select Trading Partner</h3>

          {error && (
            <div style={{ background: '#ffebee', color: '#c62828', padding: '0.8rem', borderRadius: '6px', marginBottom: '1rem' }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
            {otherPlayers.map(player => (
              <div
                key={player.game_player_id}
                onClick={() => setSelectedCounterparty(String(player.game_player_id))}
                style={{
                  padding: '1rem',
                  border: selectedCounterparty === String(player.game_player_id) ? '3px solid #6a4c93' : '2px solid #ddd',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  background: selectedCounterparty === String(player.game_player_id) ? '#f3e5f5' : '#fff'
                }}
              >
                <strong>{player.player_name}</strong>
                <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.3rem' }}>
                  Cash: ${playerBalances[String(player.game_player_id)] ?? 0}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', padding: '1rem', borderTop: '1px solid #ddd' }}>
          <button onClick={onClose} style={btnStyle('#dc3545')}>Cancel</button>
          <button
            onClick={initiateTrade}
            disabled={!selectedCounterparty || isInitiating}
            style={btnStyle(!selectedCounterparty || isInitiating ? '#ccc' : '#28a745')}
          >
            {isInitiating ? 'Starting...' : 'Start Trade'}
          </button>
        </div>
      </div>
    );
  }

  // Pending invite (counterparty)
  if (activeTrade.status === 'pending_invite' && isCounterparty) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '2rem', justifyContent: 'center', alignItems: 'center' }}>
        <h3>{initiatorPlayer?.player_name} has invited you to trade!</h3>
        <p style={{ color: '#666', marginBottom: '2rem' }}>Do you want to accept this trade invitation?</p>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button onClick={() => acceptInvite(false)} style={btnStyle('#dc3545')}>Decline</button>
          <button onClick={() => acceptInvite(true)} style={btnStyle('#28a745')}>Accept</button>
        </div>
      </div>
    );
  }

  // Waiting (initiator)
  if (activeTrade.status === 'pending_invite' && isInitiator) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '2rem', justifyContent: 'center', alignItems: 'center' }}>
        <h3>Waiting for {counterpartyPlayer?.player_name} to accept...</h3>
        <p style={{ color: '#666', marginBottom: '2rem' }}>The trade will begin once they accept your invitation.</p>
        <button onClick={cancelTrade} style={btnStyle('#dc3545')}>Cancel Trade</button>
      </div>
    );
  }

  // Active trading screen
  const actualInitiatorCash = activeTrade?.initiator_offer?.cash || 0;
  const actualInitiatorRams = activeTrade?.initiator_offer?.stud_ram_space_ids || [];
  const actualCounterpartyCash = activeTrade?.counterparty_offer?.cash || 0;
  const actualCounterpartyRams = activeTrade?.counterparty_offer?.stud_ram_space_ids || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      {activeTrade?.status === 'completed' && (
        <div style={{ background: '#d4edda', color: '#155724', padding: '1.5rem', margin: '1rem', borderRadius: '6px', fontWeight: 'bold', textAlign: 'center', fontSize: '1.1rem' }}>
          Trade completed successfully!
          <div style={{ marginTop: '1rem' }}>
            <button onClick={onClose} style={btnStyle('#28a745')}>Close</button>
          </div>
        </div>
      )}
      {activeTrade?.status === 'cancelled' && (
        <div style={{ background: '#fff3cd', color: '#856404', padding: '1rem', margin: '1rem', borderRadius: '6px', fontWeight: 'bold', textAlign: 'center' }}>
          This trade was cancelled.
        </div>
      )}
      {error && (
        <div style={{ background: '#ffebee', color: '#c62828', padding: '0.8rem', margin: '1rem', borderRadius: '6px' }}>
          {error}
        </div>
      )}

      {activeTrade?.status === 'completed' ? null : (
        <>
          {/* Trade Summary */}
          <div style={{ margin: '1rem', padding: '1rem', background: '#e3f2fd', border: '2px solid #2196f3', borderRadius: '8px' }}>
            <h3 style={{ marginTop: 0, color: '#1565c0', textAlign: 'center' }}>Trade Summary</h3>
            <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', gap: '2rem' }}>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: '#6a4c93' }}>
                  {initiatorPlayer?.player_name} Offers:
                </div>
                {actualInitiatorCash > 0 && <div>${actualInitiatorCash}</div>}
                {actualInitiatorRams.length > 0 && (
                  <div>{actualInitiatorRams.length} Stud Ram{actualInitiatorRams.length > 1 ? 's' : ''}</div>
                )}
                {actualInitiatorCash === 0 && actualInitiatorRams.length === 0 && (
                  <div style={{ color: '#999', fontStyle: 'italic' }}>Nothing</div>
                )}
              </div>

              <div style={{ fontSize: '2rem' }}>&#x27F7;</div>

              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: '#ff924c' }}>
                  {counterpartyPlayer?.player_name} Offers:
                </div>
                {actualCounterpartyCash > 0 && <div>${actualCounterpartyCash}</div>}
                {actualCounterpartyRams.length > 0 && (
                  <div>{actualCounterpartyRams.length} Stud Ram{actualCounterpartyRams.length > 1 ? 's' : ''}</div>
                )}
                {actualCounterpartyCash === 0 && actualCounterpartyRams.length === 0 && (
                  <div style={{ color: '#999', fontStyle: 'italic' }}>Nothing</div>
                )}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flex: 1, gap: '1rem', padding: '1rem' }}>
            {/* Left Side - Initiator */}
            <div style={{ flex: 1, border: '2px solid #6a4c93', borderRadius: '8px', padding: '1rem', background: '#fafafa' }}>
              <h3 style={{ marginTop: 0, color: '#6a4c93' }}>{initiatorPlayer?.player_name}</h3>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                  Cash (Available: ${initiatorBalance})
                </label>
                <input
                  type="number"
                  value={initiatorCash}
                  onChange={(e) => setInitiatorCash(Math.max(0, Math.min(parseInt(e.target.value) || 0, initiatorBalance)))}
                  disabled={!isInitiator}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '1rem' }}
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>Stud Rams</label>
                <div style={{ maxHeight: '150px', overflowY: 'auto', border: '1px solid #ddd', borderRadius: '4px', padding: '0.5rem', background: '#fff' }}>
                  {initiatorRams.length > 0 ? initiatorRams.map(ram => (
                    <label key={ram.space_id} style={{ display: 'block', marginBottom: '0.5rem', cursor: isInitiator ? 'pointer' : 'default' }}>
                      <input
                        type="checkbox"
                        checked={initiatorStudRamIds.includes(ram.space_id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setInitiatorStudRamIds([...initiatorStudRamIds, ram.space_id]);
                          } else {
                            setInitiatorStudRamIds(initiatorStudRamIds.filter(id => id !== ram.space_id));
                          }
                        }}
                        disabled={!isInitiator}
                        style={{ marginRight: '0.5rem' }}
                      />
                      {ram.space_name} (Fee: ${ram.stud_fee})
                    </label>
                  )) : <div style={{ color: '#999', fontStyle: 'italic' }}>No stud rams owned</div>}
                </div>
              </div>

              {isInitiator && (
                <button
                  onClick={() => updateOffer(true)}
                  disabled={activeTrade?.status === 'cancelled'}
                  style={btnStyle(activeTrade?.status === 'cancelled' ? '#ccc' : '#1982c4')}
                >
                  Update My Offer
                </button>
              )}
            </div>

            {/* Right Side - Counterparty */}
            <div style={{ flex: 1, border: '2px solid #ff924c', borderRadius: '8px', padding: '1rem', background: '#fafafa' }}>
              <h3 style={{ marginTop: 0, color: '#ff924c' }}>{counterpartyPlayer?.player_name}</h3>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                  Cash (Available: ${counterpartyBalance})
                </label>
                <input
                  type="number"
                  value={counterpartyCash}
                  onChange={(e) => setCounterpartyCash(Math.max(0, Math.min(parseInt(e.target.value) || 0, counterpartyBalance)))}
                  disabled={!isCounterparty}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '1rem' }}
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>Stud Rams</label>
                <div style={{ maxHeight: '150px', overflowY: 'auto', border: '1px solid #ddd', borderRadius: '4px', padding: '0.5rem', background: '#fff' }}>
                  {counterpartyRams.length > 0 ? counterpartyRams.map(ram => (
                    <label key={ram.space_id} style={{ display: 'block', marginBottom: '0.5rem', cursor: isCounterparty ? 'pointer' : 'default' }}>
                      <input
                        type="checkbox"
                        checked={counterpartyStudRamIds.includes(ram.space_id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setCounterpartyStudRamIds([...counterpartyStudRamIds, ram.space_id]);
                          } else {
                            setCounterpartyStudRamIds(counterpartyStudRamIds.filter(id => id !== ram.space_id));
                          }
                        }}
                        disabled={!isCounterparty}
                        style={{ marginRight: '0.5rem' }}
                      />
                      {ram.space_name} (Fee: ${ram.stud_fee})
                    </label>
                  )) : <div style={{ color: '#999', fontStyle: 'italic' }}>No stud rams owned</div>}
                </div>
              </div>

              {isCounterparty && (
                <button
                  onClick={() => updateOffer(false)}
                  disabled={activeTrade?.status === 'cancelled'}
                  style={btnStyle(activeTrade?.status === 'cancelled' ? '#ccc' : '#1982c4')}
                >
                  Update My Offer
                </button>
              )}
            </div>
          </div>

          {/* Acceptance Status */}
          <div style={{ padding: '1rem', background: '#f5f5f5', borderTop: '1px solid #ddd' }}>
            <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>{initiatorPlayer?.player_name}</div>
                <div style={{
                  padding: '0.5rem 1rem',
                  background: activeTrade?.initiator_accepted ? '#4caf50' : '#ff9800',
                  color: '#fff', borderRadius: '20px', fontWeight: 'bold', fontSize: '0.9rem'
                }}>
                  {activeTrade?.initiator_accepted ? 'Accepted' : 'Pending'}
                </div>
              </div>
              <div style={{ fontSize: '1.5rem', color: '#999' }}>&#x27F7;</div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>{counterpartyPlayer?.player_name}</div>
                <div style={{
                  padding: '0.5rem 1rem',
                  background: activeTrade?.counterparty_accepted ? '#4caf50' : '#ff9800',
                  color: '#fff', borderRadius: '20px', fontWeight: 'bold', fontSize: '0.9rem'
                }}>
                  {activeTrade?.counterparty_accepted ? 'Accepted' : 'Pending'}
                </div>
              </div>
            </div>
            {!(activeTrade?.initiator_accepted && activeTrade?.counterparty_accepted) && (
              <div style={{ textAlign: 'center', fontSize: '0.85rem', color: '#666', fontStyle: 'italic' }}>
                Both parties must accept before the trade can be executed
              </div>
            )}
          </div>

          {/* Bottom buttons */}
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', padding: '1rem', borderTop: '1px solid #ddd' }}>
            <button onClick={cancelTrade} style={btnStyle('#dc3545')}>Cancel Trade</button>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={acceptTrade}
                disabled={
                  (isInitiator && activeTrade?.initiator_accepted) ||
                  (isCounterparty && activeTrade?.counterparty_accepted)
                }
                style={btnStyle(
                  (isInitiator && activeTrade?.initiator_accepted) ||
                  (isCounterparty && activeTrade?.counterparty_accepted)
                    ? '#ccc' : '#ff9800'
                )}
              >
                {(isInitiator && activeTrade?.initiator_accepted) || (isCounterparty && activeTrade?.counterparty_accepted)
                  ? 'Accepted' : 'Accept Trade'}
              </button>

              <button
                onClick={executeTrade}
                disabled={!(activeTrade?.initiator_accepted && activeTrade?.counterparty_accepted)}
                style={btnStyle(
                  !(activeTrade?.initiator_accepted && activeTrade?.counterparty_accepted) ? '#ccc' : '#28a745'
                )}
              >
                Execute Trade
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

const btnStyle = (bg) => ({
  padding: '0.6rem 1.5rem',
  background: bg,
  color: '#fff',
  border: 'none',
  borderRadius: '6px',
  cursor: bg === '#ccc' ? 'not-allowed' : 'pointer',
  fontSize: '1rem',
  fontWeight: 'bold'
});
