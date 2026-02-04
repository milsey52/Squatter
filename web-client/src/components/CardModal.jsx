import { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function CardModal({ gameId, sessionToken, userId, pendingAction, players, onResolved }) {
  const [acknowledging, setAcknowledging] = useState(false);

  if (!pendingAction || pendingAction.action_type !== 'card_drawn') {
    return null;
  }

  let cardData = {};
  try {
    cardData = JSON.parse(pendingAction.action_data || '{}');
  } catch (e) {
    console.error('Error parsing card data:', e);
    cardData = {};
  }

  const isChance = cardData.deck_type === 'chance';
  const bgColor = isChance ? '#ff924c' : '#6a4c93';

  // Check if the logged-in user is the active player
  const activePlayer = players?.find(p => p.game_player_id === pendingAction.active_player_id);
  const isActivePlayer = activePlayer?.user_id === userId;

  // Debug: Log card data
  console.log('[CardModal] Card data:', cardData);

  const handleAcknowledge = async () => {
    setAcknowledging(true);
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/decisions/acknowledge-card`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to acknowledge card');
      }

      if (onResolved) onResolved();
    } catch (error) {
      console.error('Error acknowledging card:', error);
      alert(error.message);
    } finally {
      setAcknowledging(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999
    }}>
      <div style={{
        background: '#fff',
        borderRadius: '12px',
        padding: '2rem',
        maxWidth: '500px',
        width: '90%',
        boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
      }}>
        {/* Header */}
        <div style={{
          background: bgColor,
          color: '#fff',
          padding: '1rem',
          borderRadius: '8px',
          marginBottom: '1.5rem',
          textAlign: 'center'
        }}>
          <h2 style={{ margin: 0, fontSize: '1.5rem' }}>
            {isChance ? '🎲 CHANCE' : '🏥 WELFARE CENTRE'}
          </h2>
        </div>

        {/* Card Content */}
        <div style={{
          background: '#f9f9f9',
          border: `3px solid ${bgColor}`,
          borderRadius: '8px',
          padding: '1.5rem',
          marginBottom: '1.5rem',
          minHeight: '150px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <div style={{ textAlign: 'center' }}>
            <h3 style={{ margin: '0 0 1rem 0', color: '#333', fontSize: '1.2rem' }}>
              {cardData.card_name || cardData.title || 'Card'}
            </h3>
            <p style={{ margin: 0, color: '#555', fontSize: '1rem', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
              {cardData.card_description || cardData.body_text || 'Follow the instructions on this card.'}
            </p>
            {(!cardData.card_name && !cardData.card_description) && (
              <div style={{ marginTop: '1rem', padding: '0.5rem', background: '#ffebee', borderRadius: '4px', fontSize: '0.85rem' }}>
                Debug: No card data received. Please report this issue.
              </div>
            )}
            {cardData.is_retainable && (
              <div style={{
                marginTop: '1rem',
                background: '#4caf50',
                color: '#fff',
                padding: '0.5rem 1rem',
                borderRadius: '6px',
                fontWeight: 'bold'
              }}>
                ✓ This card has been added to your collection
              </div>
            )}
          </div>
        </div>

        {/* Waiting message for non-active players */}
        {!isActivePlayer && (
          <div style={{
            background: '#fff3cd',
            color: '#856404',
            padding: '0.75rem 1rem',
            borderRadius: '6px',
            marginBottom: '1rem',
            fontSize: '0.95rem',
            fontWeight: 'bold',
            textAlign: 'center'
          }}>
            ⏳ Waiting for {activePlayer?.player_name || "player"} to continue...
          </div>
        )}

        {/* Action Button */}
        <button
          onClick={handleAcknowledge}
          disabled={acknowledging || !isActivePlayer}
          style={{
            width: '100%',
            padding: '1rem',
            background: acknowledging || !isActivePlayer ? '#ccc' : bgColor,
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontSize: '1.1rem',
            fontWeight: 'bold',
            cursor: acknowledging || !isActivePlayer ? 'not-allowed' : 'pointer',
            opacity: acknowledging || !isActivePlayer ? 0.6 : 1
          }}
        >
          {acknowledging ? 'Processing...' : 'Continue'}
        </button>
      </div>
    </div>
  );
}
