import { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function RentPaymentModal({ gameId, sessionToken, pendingAction, playerBalances, onResolved, onBankruptcy, userId, players, onDismiss }) {
  const [paying, setPaying] = useState(false);

  if (!pendingAction || pendingAction.action_type !== 'rent_payment') {
    return null;
  }

  const rentData = JSON.parse(pendingAction.action_data || '{}');
  const rentAmount = rentData.rent_amount || 0;
  const landlordName = rentData.landlord_name || 'Another Player';
  const propertyName = rentData.property_name || 'Property';

  const currentBalance = playerBalances[String(pendingAction.active_player_id)] || 0;
  const canAfford = currentBalance >= rentAmount;

  // Find current user's player and debtor player
  // Use loose equality to handle type mismatches (string vs number)
  const currentUserPlayer = players?.find(p => p.user_id == userId);
  const debtorPlayer = players?.find(p => p.game_player_id == pendingAction.active_player_id);
  const isDebtor = currentUserPlayer && currentUserPlayer.game_player_id == pendingAction.active_player_id;

  const handlePayRent = async () => {
    setPaying(true);
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/decisions/pay-rent`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (response.status === 402) {
        // Payment required - player is bankrupt
        const debtData = await response.json();
        if (onBankruptcy) {
          onBankruptcy(debtData.detail);
        }
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to pay rent');
      }

      if (onResolved) onResolved();
    } catch (error) {
      console.error('Error paying rent:', error);
      alert(error.message);
    } finally {
      setPaying(false);
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
          background: '#d32f2f',
          color: '#fff',
          padding: '1rem',
          borderRadius: '8px',
          marginBottom: '1.5rem',
          textAlign: 'center'
        }}>
          <h2 style={{ margin: 0, fontSize: '1.5rem' }}>
            💰 RENT DUE
          </h2>
        </div>

        {/* Rent Details */}
        <div style={{
          background: '#fff3e0',
          border: '3px solid #ff9800',
          borderRadius: '8px',
          padding: '1.5rem',
          marginBottom: '1.5rem'
        }}>
          <div style={{ marginBottom: '1rem', color: '#333' }}>
            <strong>Property:</strong> {propertyName}
          </div>
          <div style={{ marginBottom: '1rem', color: '#333' }}>
            <strong>Owner:</strong> {landlordName}
          </div>
          <div style={{
            fontSize: '2rem',
            fontWeight: 'bold',
            color: '#d32f2f',
            textAlign: 'center',
            padding: '1rem',
            background: '#fff',
            borderRadius: '6px'
          }}>
            ${rentAmount}
          </div>
        </div>

        {/* Balance Warning */}
        {!canAfford && (
          <div style={{
            background: '#ffebee',
            border: '2px solid #f44336',
            borderRadius: '6px',
            padding: '1rem',
            marginBottom: '1rem',
            color: '#c62828'
          }}>
            ⚠️ Warning: Insufficient funds! (Balance: ${currentBalance})
          </div>
        )}

        {/* Current Balance */}
        <div style={{
          marginBottom: '1.5rem',
          padding: '0.75rem',
          background: '#f5f5f5',
          borderRadius: '6px',
          textAlign: 'center',
          color: '#555'
        }}>
          Your Balance: <strong style={{ color: canAfford ? '#4caf50' : '#f44336' }}>${currentBalance}</strong>
        </div>

        {/* Action Button */}
        {isDebtor ? (
          <>
            <button
              onClick={handlePayRent}
              disabled={paying}
              style={{
                width: '100%',
                padding: '1rem',
                background: paying ? '#ccc' : '#d32f2f',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '1.1rem',
                fontWeight: 'bold',
                cursor: paying ? 'not-allowed' : 'pointer'
              }}
            >
              {paying ? 'Processing...' : `Pay $${rentAmount}`}
            </button>

            {!canAfford && (
              <p style={{
                marginTop: '1rem',
                textAlign: 'center',
                color: '#999',
                fontSize: '0.9rem'
              }}>
                You may need to mortgage properties or sell houses to pay this rent.
              </p>
            )}
          </>
        ) : (
          <>
            <p style={{
              marginBottom: '1rem',
              textAlign: 'center',
              color: '#d32f2f',
              fontSize: '1rem',
              fontWeight: 'bold'
            }}>
              Waiting for {debtorPlayer?.player_name || 'the player'} to pay...
            </p>

            <button
              onClick={onDismiss}
              style={{
                width: '100%',
                padding: '1rem',
                background: '#6c757d',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '1.1rem',
                fontWeight: 'bold',
                cursor: 'pointer'
              }}
            >
              Dismiss (Continue Playing)
            </button>

            <p style={{
              marginTop: '0.75rem',
              textAlign: 'center',
              color: '#666',
              fontSize: '0.85rem'
            }}>
              You can dismiss this and continue playing while waiting for payment.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
