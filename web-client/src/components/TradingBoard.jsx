import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function TradingBoard({ gameId, sessionToken, userId, game, playerBalances, allPlayerAssets, playerRetainedCards, onClose, activeTradeFromParent }) {
  const [activeTrade, setActiveTrade] = useState(activeTradeFromParent);
  const [selectedCounterparty, setSelectedCounterparty] = useState(null);
  const [isInitiating, setIsInitiating] = useState(false);
  const [error, setError] = useState(null);

  // Initiator's offer
  const [initiatorCash, setInitiatorCash] = useState(0);
  const [initiatorPropertyIds, setInitiatorPropertyIds] = useState([]);
  const [initiatorCardIds, setInitiatorCardIds] = useState([]);

  // Counterparty's offer
  const [counterpartyCash, setCounterpartyCash] = useState(0);
  const [counterpartyPropertyIds, setCounterpartyPropertyIds] = useState([]);
  const [counterpartyCardIds, setCounterpartyCardIds] = useState([]);

  const currentUserPlayer = game.players?.find(p => p.user_id === userId);

  // Sync with parent's active trade
  useEffect(() => {
    setActiveTrade(activeTradeFromParent);

    // Update offers when trade changes
    if (activeTradeFromParent) {
      if (activeTradeFromParent.initiator_offer) {
        setInitiatorCash(activeTradeFromParent.initiator_offer.cash || 0);
        setInitiatorPropertyIds(activeTradeFromParent.initiator_offer.properties || []);
        setInitiatorCardIds(activeTradeFromParent.initiator_offer.cards || []);
      }
      if (activeTradeFromParent.counterparty_offer) {
        setCounterpartyCash(activeTradeFromParent.counterparty_offer.cash || 0);
        setCounterpartyPropertyIds(activeTradeFromParent.counterparty_offer.properties || []);
        setCounterpartyCardIds(activeTradeFromParent.counterparty_offer.cards || []);
      }
    }
  }, [activeTradeFromParent]);

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
          counterparty_player_id: selectedCounterparty === 'bank' ? null : parseInt(selectedCounterparty)
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to initiate trade');
      }

      const data = await response.json();

      // Immediately set the active trade from response
      // (SSE event will also trigger an update, but this provides instant feedback)
      setActiveTrade({
        trade_session_id: data.trade_session_id,
        game_id: gameId,
        initiator_player_id: data.initiator_player_id,
        counterparty_player_id: data.counterparty_player_id,
        status: data.status,
        initiator_offer: { cash: 0, properties: [], cards: [] },
        counterparty_offer: { cash: 0, properties: [], cards: [] },
        created_at: new Date().toISOString()
      });

      // Reset offer states
      setInitiatorCash(0);
      setInitiatorPropertyIds([]);
      setInitiatorCardIds([]);
      setCounterpartyCash(0);
      setCounterpartyPropertyIds([]);
      setCounterpartyCardIds([]);
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
          property_ids: isInitiator ? initiatorPropertyIds : counterpartyPropertyIds,
          card_ids: isInitiator ? initiatorCardIds : counterpartyCardIds
        })
      });

      if (!response.ok) throw new Error('Failed to update offer');
      // Offer state will be updated via SSE event
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
          headers: {
            'Authorization': `Bearer ${sessionToken}`
          }
        }
      );

      if (!response.ok) throw new Error('Failed to respond to invite');

      // Trade state will be updated via SSE event
      if (!accept) {
        onClose();
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const cancelTrade = async () => {
    if (!activeTrade) return;

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/trades/${activeTrade.trade_session_id}/cancel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
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
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to accept trade');
      }

      // Acceptance state will be updated via SSE event
    } catch (err) {
      setError(err.message);
    }
  };

  const executeTrade = async () => {
    if (!activeTrade) return;

    try {
      // For Bank trades, first update the offer with selected properties
      const isBankTrade = activeTrade.counterparty_player_id === null;
      const isUserInitiator = currentUserPlayer && activeTrade.initiator_player_id === currentUserPlayer.game_player_id;

      if (isBankTrade && isUserInitiator) {
        const updateResponse = await fetch(`${API_BASE}/games/${gameId}/trades/${activeTrade.trade_session_id}/update-offer`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${sessionToken}`
          },
          body: JSON.stringify({
            cash: 0,
            property_ids: initiatorPropertyIds,
            card_ids: []
          })
        });

        if (!updateResponse.ok) {
          const errorData = await updateResponse.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Failed to update offer');
        }
      }

      // Now execute the trade
      const response = await fetch(`${API_BASE}/games/${gameId}/trades/${activeTrade.trade_session_id}/execute`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
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
  const isBank = activeTrade && activeTrade.counterparty_player_id === null;

  // Get player data
  const initiatorPlayer = activeTrade ? game.players.find(p => p.game_player_id === activeTrade.initiator_player_id) : currentUserPlayer;
  const counterpartyPlayer = activeTrade && activeTrade.counterparty_player_id ?
    game.players.find(p => p.game_player_id === activeTrade.counterparty_player_id) : null;

  const initiatorAssets = initiatorPlayer ? (allPlayerAssets[initiatorPlayer.game_player_id] || []) : [];
  const counterpartyAssets = counterpartyPlayer ? (allPlayerAssets[counterpartyPlayer.game_player_id] || []) : [];

  const initiatorCards = initiatorPlayer ? (playerRetainedCards[initiatorPlayer.game_player_id] || []) : [];
  const counterpartyCards = counterpartyPlayer ? (playerRetainedCards[counterpartyPlayer.game_player_id] || []) : [];

  const initiatorBalance = initiatorPlayer ? (playerBalances[String(initiatorPlayer.game_player_id)] ?? 0) : 0;
  const counterpartyBalance = counterpartyPlayer ? (playerBalances[String(counterpartyPlayer.game_player_id)] ?? 0) : 0;

  // Render counterparty selection screen
  if (!activeTrade) {
    const otherPlayers = game.players.filter(p => p.game_player_id !== currentUserPlayer?.game_player_id);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
        <div style={{ flex: 1, padding: '1rem' }}>
          <h3 style={{ marginTop: 0 }}>Select Trading Partner</h3>

          {error && (
            <div style={{
              background: '#ffebee',
              color: '#c62828',
              padding: '0.8rem',
              borderRadius: '6px',
              marginBottom: '1rem'
            }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
            <div
              onClick={() => setSelectedCounterparty('bank')}
              style={{
                padding: '1rem',
                border: selectedCounterparty === 'bank' ? '3px solid #6a4c93' : '2px solid #ddd',
                borderRadius: '8px',
                cursor: 'pointer',
                background: selectedCounterparty === 'bank' ? '#f3e5f5' : '#fff'
              }}
            >
              <strong>Bank</strong>
              <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.3rem' }}>
                Trade with the Bank (no acceptance needed)
              </div>
            </div>

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
          <button
            onClick={onClose}
            style={{
              padding: '0.6rem 1.5rem',
              background: '#dc3545',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '1rem',
              fontWeight: 'bold'
            }}
          >
            Cancel
          </button>
          <button
            onClick={initiateTrade}
            disabled={!selectedCounterparty || isInitiating}
            style={{
              padding: '0.6rem 1.5rem',
              background: !selectedCounterparty || isInitiating ? '#ccc' : '#28a745',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: !selectedCounterparty || isInitiating ? 'not-allowed' : 'pointer',
              fontSize: '1rem',
              fontWeight: 'bold'
            }}
          >
            {isInitiating ? 'Starting...' : 'Start Trade'}
          </button>
        </div>
      </div>
    );
  }

  // Render pending invite screen (for counterparty)
  if (activeTrade.status === 'pending_invite' && isCounterparty) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '2rem', justifyContent: 'center', alignItems: 'center' }}>
        <h3>{initiatorPlayer?.player_name} has invited you to trade!</h3>
        <p style={{ color: '#666', marginBottom: '2rem' }}>Do you want to accept this trade invitation?</p>

        <div style={{ display: 'flex', gap: '1rem' }}>
          <button
            onClick={() => acceptInvite(false)}
            style={{
              padding: '0.8rem 2rem',
              background: '#dc3545',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '1.1rem',
              fontWeight: 'bold'
            }}
          >
            Decline
          </button>
          <button
            onClick={() => acceptInvite(true)}
            style={{
              padding: '0.8rem 2rem',
              background: '#28a745',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '1.1rem',
              fontWeight: 'bold'
            }}
          >
            Accept
          </button>
        </div>
      </div>
    );
  }

  // Render waiting screen (for initiator while counterparty hasn't accepted)
  if (activeTrade.status === 'pending_invite' && isInitiator) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '2rem', justifyContent: 'center', alignItems: 'center' }}>
        <h3>Waiting for {counterpartyPlayer?.player_name} to accept...</h3>
        <p style={{ color: '#666', marginBottom: '2rem' }}>The trade will begin once they accept your invitation.</p>

        <button
          onClick={cancelTrade}
          style={{
            padding: '0.8rem 2rem',
            background: '#dc3545',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '1.1rem',
            fontWeight: 'bold'
          }}
        >
          Cancel Trade
        </button>
      </div>
    );
  }

  // Render active trading screen
  // Get the actual property names for the offers - READ FROM activeTrade, not local state
  const getOfferedProperties = (propertyIds, assets) => {
    return propertyIds.map(id => assets.find(a => a.asset_id === id)).filter(Boolean);
  };

  // Use the actual trade data for the summary, not local state
  const actualInitiatorCash = activeTrade?.initiator_offer?.cash || 0;
  const actualInitiatorProperties = activeTrade?.initiator_offer?.properties || [];
  const actualInitiatorCards = activeTrade?.initiator_offer?.cards || [];

  const actualCounterpartyCash = activeTrade?.counterparty_offer?.cash || 0;
  const actualCounterpartyProperties = activeTrade?.counterparty_offer?.properties || [];
  const actualCounterpartyCards = activeTrade?.counterparty_offer?.cards || [];

  const initiatorOfferedProperties = getOfferedProperties(actualInitiatorProperties, initiatorAssets);
  const counterpartyOfferedProperties = getOfferedProperties(actualCounterpartyProperties, counterpartyAssets);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      {activeTrade?.status === 'completed' && (
        <div style={{
          background: '#d4edda',
          color: '#155724',
          padding: '1.5rem',
          margin: '1rem',
          borderRadius: '6px',
          fontWeight: 'bold',
          textAlign: 'center',
          fontSize: '1.1rem'
        }}>
          ✅ Trade completed successfully! Properties have been transferred.
          <div style={{ marginTop: '1rem' }}>
            <button
              onClick={onClose}
              style={{
                padding: '0.6rem 1.5rem',
                background: '#28a745',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: 'bold'
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}
      {activeTrade?.status === 'cancelled' && (
        <div style={{
          background: '#fff3cd',
          color: '#856404',
          padding: '1rem',
          margin: '1rem',
          borderRadius: '6px',
          fontWeight: 'bold',
          textAlign: 'center'
        }}>
          ⚠️ This trade was cancelled. Please close and start a new trade.
        </div>
      )}
      {error && (
        <div style={{
          background: '#ffebee',
          color: '#c62828',
          padding: '0.8rem',
          margin: '1rem',
          borderRadius: '6px'
        }}>
          {error}
        </div>
      )}

      {/* Hide all trade UI if trade is completed */}
      {activeTrade?.status === 'completed' ? null : (
        <>
      {/* Trade Summary - Only for player-to-player trades */}
      {!isBank && (
        <div style={{ margin: '1rem', padding: '1rem', background: '#e3f2fd', border: '2px solid #2196f3', borderRadius: '8px' }}>
          <h3 style={{ marginTop: 0, color: '#1565c0', textAlign: 'center' }}>Trade Summary</h3>
          <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', gap: '2rem' }}>
            {/* Initiator's Offer */}
            <div style={{ flex: 1, textAlign: 'center' }}>
              <div style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: '#6a4c93' }}>
                {initiatorPlayer?.player_name} Offers:
              </div>
              {actualInitiatorCash > 0 && (
                <div style={{ marginBottom: '0.3rem' }}>💰 ${actualInitiatorCash}</div>
              )}
              {initiatorOfferedProperties.length > 0 && (
                <div style={{ marginBottom: '0.3rem' }}>
                  🏠 {initiatorOfferedProperties.map(p => p.name).join(', ')}
                </div>
              )}
              {actualInitiatorCards.length > 0 && (
                <div style={{ marginBottom: '0.3rem' }}>
                  🎫 {actualInitiatorCards.length} Get Out of Jail Card{actualInitiatorCards.length > 1 ? 's' : ''}
                </div>
              )}
              {actualInitiatorCash === 0 && initiatorOfferedProperties.length === 0 && actualInitiatorCards.length === 0 && (
                <div style={{ color: '#999', fontStyle: 'italic' }}>Nothing</div>
              )}
            </div>

            <div style={{ fontSize: '2rem' }}>⟷</div>

            {/* Counterparty's Offer */}
            <div style={{ flex: 1, textAlign: 'center' }}>
              <div style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: '#ff924c' }}>
                {counterpartyPlayer?.player_name} Offers:
              </div>
              {actualCounterpartyCash > 0 && (
                <div style={{ marginBottom: '0.3rem' }}>💰 ${actualCounterpartyCash}</div>
              )}
              {counterpartyOfferedProperties.length > 0 && (
                <div style={{ marginBottom: '0.3rem' }}>
                  🏠 {counterpartyOfferedProperties.map(p => p.name).join(', ')}
                </div>
              )}
              {actualCounterpartyCards.length > 0 && (
                <div style={{ marginBottom: '0.3rem' }}>
                  🎫 {actualCounterpartyCards.length} Get Out of Jail Card{actualCounterpartyCards.length > 1 ? 's' : ''}
                </div>
              )}
              {actualCounterpartyCash === 0 && counterpartyOfferedProperties.length === 0 && actualCounterpartyCards.length === 0 && (
                <div style={{ color: '#999', fontStyle: 'italic' }}>Nothing</div>
              )}
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flex: 1, gap: '1rem', padding: '1rem' }}>
        {/* Left Side - Initiator */}
        <div style={{ flex: 1, border: '2px solid #6a4c93', borderRadius: '8px', padding: '1rem', background: '#fafafa' }}>
          <h3 style={{ marginTop: 0, color: '#6a4c93' }}>{initiatorPlayer?.player_name} (Initiator)</h3>

          {/* Cash - Hidden for Bank trades */}
          {!isBank && (
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                Cash (Available: ${initiatorBalance})
              </label>
              <input
                type="number"
                value={initiatorCash}
                onChange={(e) => setInitiatorCash(Math.max(0, Math.min(parseInt(e.target.value) || 0, initiatorBalance)))}
                disabled={!isInitiator}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  borderRadius: '4px',
                  border: '1px solid #ccc',
                  fontSize: '1rem'
                }}
              />
            </div>
          )}

          {/* Properties */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>
              {isBank ? 'Select Properties to Mortgage' : 'Properties'}
            </label>
            <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid #ddd', borderRadius: '4px', padding: '0.5rem', background: '#fff' }}>
              {initiatorAssets.length > 0 ? initiatorAssets.map(asset => {
                const canMortgage = isBank && !asset.is_mortgaged && asset.improvement_level === 0 && !asset.has_hotel;
                const isDisabled = isBank && !canMortgage;

                return (
                  <label
                    key={asset.asset_id}
                    style={{
                      display: 'block',
                      marginBottom: '0.5rem',
                      cursor: (isInitiator && !isDisabled) ? 'pointer' : 'default',
                      opacity: isDisabled ? 0.5 : 1,
                      background: asset.is_mortgaged ? '#ffe0e0' : 'transparent',
                      padding: '0.25rem',
                      borderRadius: '4px'
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={initiatorPropertyIds.includes(asset.asset_id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setInitiatorPropertyIds([...initiatorPropertyIds, asset.asset_id]);
                        } else {
                          setInitiatorPropertyIds(initiatorPropertyIds.filter(id => id !== asset.asset_id));
                        }
                      }}
                      disabled={!isInitiator || isDisabled}
                      style={{ marginRight: '0.5rem' }}
                    />
                    {asset.name} - ${isBank ? asset.mortgage_value : asset.purchase_price}
                    {!isBank && asset.improvement_level > 0 && ` (${asset.improvement_level} house${asset.improvement_level > 1 ? 's' : ''})`}
                    {!isBank && asset.has_hotel && ' (hotel)'}
                    {asset.is_mortgaged && <span style={{ color: '#d32f2f', fontWeight: 'bold' }}> [MORTGAGED]</span>}
                    {isBank && !asset.is_mortgaged && <span style={{ color: '#2e7d32', fontWeight: 'bold' }}> (Mortgage: ${asset.mortgage_value})</span>}
                    {isBank && (asset.improvement_level > 0 || asset.has_hotel) && <span style={{ color: '#f57c00', fontSize: '0.85rem' }}> [Has improvements]</span>}
                  </label>
                );
              }) : <div style={{ color: '#999', fontStyle: 'italic' }}>No properties</div>}
            </div>
          </div>

          {/* Cards - Hidden for Bank trades */}
          {!isBank && (
            <div>
              <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>Get Out of Jail Cards</label>
              <div style={{ maxHeight: '100px', overflowY: 'auto', border: '1px solid #ddd', borderRadius: '4px', padding: '0.5rem', background: '#fff' }}>
                {initiatorCards.length > 0 ? initiatorCards.map((card, idx) => (
                  <label key={idx} style={{ display: 'block', marginBottom: '0.5rem', cursor: isInitiator ? 'pointer' : 'default' }}>
                    <input
                      type="checkbox"
                      checked={initiatorCardIds.includes(card.card_draw_id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setInitiatorCardIds([...initiatorCardIds, card.card_draw_id]);
                        } else {
                          setInitiatorCardIds(initiatorCardIds.filter(id => id !== card.card_draw_id));
                        }
                      }}
                      disabled={!isInitiator}
                      style={{ marginRight: '0.5rem' }}
                    />
                    {card.title || card.name}
                  </label>
                )) : <div style={{ color: '#999', fontStyle: 'italic' }}>No cards</div>}
              </div>
            </div>
          )}

          {isInitiator && (
            <button
              onClick={() => updateOffer(true)}
              disabled={activeTrade?.status === 'cancelled'}
              style={{
                marginTop: '1rem',
                width: '100%',
                padding: '0.6rem',
                background: activeTrade?.status === 'cancelled' ? '#ccc' : '#1982c4',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: activeTrade?.status === 'cancelled' ? 'not-allowed' : 'pointer',
                fontWeight: 'bold'
              }}
            >
              Update My Offer
            </button>
          )}
        </div>

        {/* Right Side - Counterparty */}
        <div style={{ flex: 1, border: '2px solid #ff924c', borderRadius: '8px', padding: '1rem', background: '#fafafa' }}>
          <h3 style={{ marginTop: 0, color: '#ff924c' }}>
            {isBank ? 'Bank' : counterpartyPlayer?.player_name}
          </h3>

          {!isBank ? (
            <>
              {/* Cash */}
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                  Cash (Available: ${counterpartyBalance})
                </label>
                <input
                  type="number"
                  value={counterpartyCash}
                  onChange={(e) => setCounterpartyCash(Math.max(0, Math.min(parseInt(e.target.value) || 0, counterpartyBalance)))}
                  disabled={!isCounterparty}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    borderRadius: '4px',
                    border: '1px solid #ccc',
                    fontSize: '1rem'
                  }}
                />
              </div>

              {/* Properties */}
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>Properties</label>
                <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid #ddd', borderRadius: '4px', padding: '0.5rem', background: '#fff' }}>
                  {counterpartyAssets.length > 0 ? counterpartyAssets.map(asset => (
                    <label key={asset.asset_id} style={{ display: 'block', marginBottom: '0.5rem', cursor: isCounterparty ? 'pointer' : 'default' }}>
                      <input
                        type="checkbox"
                        checked={counterpartyPropertyIds.includes(asset.asset_id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setCounterpartyPropertyIds([...counterpartyPropertyIds, asset.asset_id]);
                          } else {
                            setCounterpartyPropertyIds(counterpartyPropertyIds.filter(id => id !== asset.asset_id));
                          }
                        }}
                        disabled={!isCounterparty}
                        style={{ marginRight: '0.5rem' }}
                      />
                      {asset.name} - ${asset.purchase_price}
                      {asset.improvement_level > 0 && ` (${asset.improvement_level} house${asset.improvement_level > 1 ? 's' : ''})`}
                      {asset.has_hotel && ' (hotel)'}
                      {asset.is_mortgaged && ' (mortgaged)'}
                    </label>
                  )) : <div style={{ color: '#999', fontStyle: 'italic' }}>No properties</div>}
                </div>
              </div>

              {/* Cards */}
              <div>
                <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>Get Out of Jail Cards</label>
                <div style={{ maxHeight: '100px', overflowY: 'auto', border: '1px solid #ddd', borderRadius: '4px', padding: '0.5rem', background: '#fff' }}>
                  {counterpartyCards.length > 0 ? counterpartyCards.map((card, idx) => (
                    <label key={idx} style={{ display: 'block', marginBottom: '0.5rem', cursor: isCounterparty ? 'pointer' : 'default' }}>
                      <input
                        type="checkbox"
                        checked={counterpartyCardIds.includes(card.card_draw_id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setCounterpartyCardIds([...counterpartyCardIds, card.card_draw_id]);
                          } else {
                            setCounterpartyCardIds(counterpartyCardIds.filter(id => id !== card.card_draw_id));
                          }
                        }}
                        disabled={!isCounterparty}
                        style={{ marginRight: '0.5rem' }}
                      />
                      {card.title || card.name}
                    </label>
                  )) : <div style={{ color: '#999', fontStyle: 'italic' }}>No cards</div>}
                </div>
              </div>

              {isCounterparty && (
                <button
                  onClick={() => updateOffer(false)}
                  disabled={activeTrade?.status === 'cancelled'}
                  style={{
                    marginTop: '1rem',
                    width: '100%',
                    padding: '0.6rem',
                    background: activeTrade?.status === 'cancelled' ? '#ccc' : '#1982c4',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: activeTrade?.status === 'cancelled' ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  Update My Offer
                </button>
              )}
            </>
          ) : (
            <div style={{ padding: '1rem' }}>
              <div style={{ background: '#fff3cd', border: '1px solid #ffc107', borderRadius: '6px', padding: '1rem', marginBottom: '1.5rem' }}>
                <strong style={{ color: '#856404' }}>Mortgage Properties</strong>
                <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: '#856404' }}>
                  Select unmortgaged properties without improvements to mortgage to the Bank.
                  The Bank will pay the mortgage value for each property.
                </p>
              </div>

              <div style={{ background: '#e8f5e9', border: '2px solid #4caf50', borderRadius: '8px', padding: '1.5rem', textAlign: 'center' }}>
                <div style={{ fontSize: '0.9rem', color: '#2e7d32', marginBottom: '0.5rem' }}>
                  Bank will pay:
                </div>
                <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#1b5e20' }}>
                  ${initiatorAssets
                    .filter(a => initiatorPropertyIds.includes(a.asset_id))
                    .reduce((sum, a) => sum + (a.mortgage_value || 0), 0)}
                </div>
                <div style={{ fontSize: '0.85rem', color: '#558b2f', marginTop: '0.5rem' }}>
                  {initiatorPropertyIds.length} {initiatorPropertyIds.length === 1 ? 'property' : 'properties'} selected
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Acceptance Status for Player-to-Player Trades */}
      {!isBank && (
        <div style={{ padding: '1rem', background: '#f5f5f5', borderTop: '1px solid #ddd' }}>
          <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', marginBottom: '1rem' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
                {initiatorPlayer?.player_name}
              </div>
              <div style={{
                padding: '0.5rem 1rem',
                background: activeTrade?.initiator_accepted ? '#4caf50' : '#ff9800',
                color: '#fff',
                borderRadius: '20px',
                fontWeight: 'bold',
                fontSize: '0.9rem'
              }}>
                {activeTrade?.initiator_accepted ? '✓ Accepted' : 'Pending'}
              </div>
            </div>
            <div style={{ fontSize: '1.5rem', color: '#999' }}>⟷</div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
                {counterpartyPlayer?.player_name}
              </div>
              <div style={{
                padding: '0.5rem 1rem',
                background: activeTrade?.counterparty_accepted ? '#4caf50' : '#ff9800',
                color: '#fff',
                borderRadius: '20px',
                fontWeight: 'bold',
                fontSize: '0.9rem'
              }}>
                {activeTrade?.counterparty_accepted ? '✓ Accepted' : 'Pending'}
              </div>
            </div>
          </div>
          {!(activeTrade?.initiator_accepted && activeTrade?.counterparty_accepted) && (
            <div style={{ textAlign: 'center', fontSize: '0.85rem', color: '#666', fontStyle: 'italic' }}>
              Both parties must accept before the trade can be executed
            </div>
          )}
        </div>
      )}

      {/* Bottom buttons */}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', padding: '1rem', borderTop: '1px solid #ddd' }}>
        <button
          onClick={cancelTrade}
          style={{
            padding: '0.6rem 1.5rem',
            background: '#dc3545',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '1rem',
            fontWeight: 'bold'
          }}
        >
          Cancel Trade
        </button>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {/* Accept Button - Only show for player-to-player trades */}
          {!isBank && (
            <button
              onClick={acceptTrade}
              disabled={
                (isInitiator && activeTrade?.initiator_accepted) ||
                (isCounterparty && activeTrade?.counterparty_accepted)
              }
              style={{
                padding: '0.6rem 1.5rem',
                background: (
                  (isInitiator && activeTrade?.initiator_accepted) ||
                  (isCounterparty && activeTrade?.counterparty_accepted)
                ) ? '#ccc' : '#ff9800',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: (
                  (isInitiator && activeTrade?.initiator_accepted) ||
                  (isCounterparty && activeTrade?.counterparty_accepted)
                ) ? 'not-allowed' : 'pointer',
                fontSize: '1rem',
                fontWeight: 'bold'
              }}
            >
              {(isInitiator && activeTrade?.initiator_accepted) || (isCounterparty && activeTrade?.counterparty_accepted)
                ? '✓ Accepted'
                : 'Accept Trade'}
            </button>
          )}

          {/* Execute Button */}
          <button
            onClick={executeTrade}
            disabled={
              (isBank && initiatorPropertyIds.length === 0) ||
              (!isBank && !(activeTrade?.initiator_accepted && activeTrade?.counterparty_accepted))
            }
            style={{
              padding: '0.6rem 1.5rem',
              background: (
                (isBank && initiatorPropertyIds.length === 0) ||
                (!isBank && !(activeTrade?.initiator_accepted && activeTrade?.counterparty_accepted))
              ) ? '#ccc' : '#28a745',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: (
                (isBank && initiatorPropertyIds.length === 0) ||
                (!isBank && !(activeTrade?.initiator_accepted && activeTrade?.counterparty_accepted))
              ) ? 'not-allowed' : 'pointer',
              fontSize: '1rem',
              fontWeight: 'bold'
            }}
          >
            {isBank ? 'Mortgage Properties' : 'Execute Trade'}
          </button>
        </div>
      </div>
        </>
      )}
    </div>
  );
}
