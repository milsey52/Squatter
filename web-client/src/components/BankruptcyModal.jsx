import { useState, useEffect } from 'react';

export default function BankruptcyModal({
  gameId,
  debtInfo,
  onClose,
  onLiquidate,
  onTrade,
  onResign,
  sessionToken
}) {
  const [liquidationPreview, setLiquidationPreview] = useState(null);
  const [currentBalance, setCurrentBalance] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showConfirmResign, setShowConfirmResign] = useState(false);

  useEffect(() => {
    fetchLiquidationPreview();
  }, [gameId, debtInfo]);

  const fetchLiquidationPreview = async () => {
    try {
      const playerId = sessionStorage.getItem('game_player_id');
      const response = await fetch(
        `/games/${gameId}/liquidation-preview?player_id=${playerId}`,
        {
          headers: {
            'Authorization': `Bearer ${sessionToken}`
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setLiquidationPreview(data);
        setCurrentBalance(data.current_balance);
      }
    } catch (error) {
      console.error('Failed to fetch liquidation preview:', error);
    }
  };

  const handleResolveDebt = async () => {
    if (currentBalance < debtInfo.amount_owed) {
      alert('You still need more funds to pay this debt. Continue liquidating assets or trade with other players.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `/games/${gameId}/bankruptcy/resolve-debt?debt_state_id=${debtInfo.debt_state_id}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${sessionToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.ok) {
        alert('Debt paid successfully!');
        onClose();
      } else {
        const error = await response.json();
        alert(`Failed to resolve debt: ${error.detail}`);
      }
    } catch (error) {
      console.error('Failed to resolve debt:', error);
      alert('An error occurred while resolving the debt.');
    } finally {
      setLoading(false);
    }
  };

  const handleResignClick = () => {
    setShowConfirmResign(true);
  };

  const handleConfirmResign = async () => {
    setLoading(true);
    try {
      const playerId = sessionStorage.getItem('game_player_id');
      const response = await fetch(
        `/games/${gameId}/bankruptcy/resign?player_id=${playerId}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${sessionToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.ok) {
        const result = await response.json();
        if (result.game_over) {
          alert('You have resigned. Game over!');
        } else {
          alert('You have resigned from the game. You can continue to observe.');
        }
        onResign();
        onClose();
      } else {
        const error = await response.json();
        alert(`Failed to resign: ${error.detail}`);
      }
    } catch (error) {
      console.error('Failed to resign:', error);
      alert('An error occurred while resigning.');
    } finally {
      setLoading(false);
    }
  };

  const canAffordDebt = currentBalance >= debtInfo.amount_owed;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.8)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 10000
    }} onClick={onClose}>
      <div style={{
        background: '#fff',
        borderRadius: '15px',
        width: '90%',
        maxWidth: '700px',
        maxHeight: '90vh',
        overflow: 'auto',
        boxShadow: '0 10px 50px rgba(0,0,0,0.5)'
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{
          background: 'linear-gradient(135deg, #d32f2f 0%, #f44336 100%)',
          color: '#fff',
          padding: '1.5rem',
          borderRadius: '15px 15px 0 0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h2 style={{ margin: 0 }}>⚠️ Insufficient Funds</h2>
          <button style={{
            background: 'transparent',
            border: '2px solid #fff',
            color: '#fff',
            borderRadius: '50%',
            width: '40px',
            height: '40px',
            fontSize: '1.5rem',
            cursor: 'pointer',
            fontWeight: 'bold'
          }} onClick={onClose}>×</button>
        </div>

        <div style={{ padding: '2rem' }}>
          <div style={{
            background: '#fff3cd',
            border: '2px solid #ffc107',
            borderRadius: '8px',
            padding: '1.5rem',
            marginBottom: '1.5rem'
          }}>
            <p style={{ margin: '0.5rem 0', color: '#333' }}>
              <strong>Reason:</strong> {debtInfo.reason}
            </p>
            {debtInfo.property_name && (
              <p style={{ margin: '0.5rem 0', color: '#333' }}>
                <strong>Property:</strong> {debtInfo.property_name}
              </p>
            )}
            <p style={{ margin: '0.5rem 0', color: '#333' }}>
              <strong>Creditor:</strong> {debtInfo.creditor_name}
            </p>

            <div style={{ marginTop: '1rem' }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '0.5rem',
                background: '#f5f5f5',
                borderRadius: '4px',
                marginBottom: '0.5rem'
              }}>
                <span>Current Balance:</span>
                <span style={{ fontWeight: 'bold' }}>${currentBalance}</span>
              </div>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '0.5rem',
                background: '#ffebee',
                borderRadius: '4px',
                marginBottom: '0.5rem'
              }}>
                <span>Amount Owed:</span>
                <span style={{ fontWeight: 'bold', color: '#d32f2f' }}>${debtInfo.amount_owed}</span>
              </div>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '0.5rem',
                background: canAffordDebt ? '#e8f5e9' : '#ffebee',
                borderRadius: '4px'
              }}>
                <span>Shortfall:</span>
                <span style={{ fontWeight: 'bold', color: canAffordDebt ? '#4caf50' : '#d32f2f' }}>
                  ${Math.max(0, debtInfo.amount_owed - currentBalance)}
                </span>
              </div>
            </div>
          </div>

          {liquidationPreview && (
            <div style={{
              background: '#e3f2fd',
              border: '2px solid #2196f3',
              borderRadius: '8px',
              padding: '1.5rem',
              marginBottom: '1.5rem'
            }}>
              <h3 style={{ margin: '0 0 1rem 0', color: '#1976d2' }}>Available Assets</h3>
              <p style={{ margin: '0 0 1rem 0', color: '#333' }}>
                You can raise up to <strong>${liquidationPreview.total_available}</strong> by liquidating assets:
              </p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {liquidationPreview.from_improvements > 0 && (
                  <li style={{ padding: '0.5rem 0', color: '#333' }}>
                    Sell improvements: <strong>${liquidationPreview.from_improvements}</strong>
                    <span style={{ color: '#666', fontSize: '0.9rem' }}> ({liquidationPreview.breakdown.properties_with_improvements.length} properties)</span>
                  </li>
                )}
                {liquidationPreview.from_mortgages > 0 && (
                  <li style={{ padding: '0.5rem 0', color: '#333' }}>
                    Mortgage properties: <strong>${liquidationPreview.from_mortgages}</strong>
                    <span style={{ color: '#666', fontSize: '0.9rem' }}> ({liquidationPreview.breakdown.mortgageable_properties.length} properties)</span>
                  </li>
                )}
                {liquidationPreview.from_cards > 0 && (
                  <li style={{ padding: '0.5rem 0', color: '#333' }}>
                    Sell Get Out of Jail cards: <strong>${liquidationPreview.from_cards}</strong>
                    <span style={{ color: '#666', fontSize: '0.9rem' }}> ({liquidationPreview.breakdown.jail_cards} cards @ $500 each)</span>
                  </li>
                )}
              </ul>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <h3 style={{ margin: '0 0 0.5rem 0' }}>Options</h3>

              <button
                style={{
                  width: '100%',
                  padding: '1rem',
                  background: loading ? '#ccc' : '#2196f3',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  marginBottom: '0.5rem'
                }}
                onClick={onLiquidate}
                disabled={loading}
              >
                Liquidate Assets
              </button>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#666' }}>
                Sell improvements, mortgage properties, or sell Get Out of Jail cards
              </p>
            </div>

            <div>
              <button
                style={{
                  width: '100%',
                  padding: '1rem',
                  background: loading ? '#ccc' : '#9c27b0',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  marginBottom: '0.5rem'
                }}
                onClick={onTrade}
                disabled={loading}
              >
                Trade Out of Debt
              </button>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#666' }}>
                Negotiate with other players to raise funds
              </p>
            </div>

            {canAffordDebt && (
              <div style={{
                background: '#e8f5e9',
                border: '2px solid #4caf50',
                borderRadius: '8px',
                padding: '1rem'
              }}>
                <button
                  style={{
                    width: '100%',
                    padding: '1rem',
                    background: loading ? '#ccc' : '#4caf50',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '1rem',
                    fontWeight: 'bold',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    marginBottom: '0.5rem'
                  }}
                  onClick={handleResolveDebt}
                  disabled={loading}
                >
                  {loading ? 'Processing...' : 'Process Payment'}
                </button>
                <p style={{ margin: 0, fontSize: '0.9rem', color: '#2e7d32', textAlign: 'center' }}>
                  ✓ You have sufficient funds to pay this debt
                </p>
              </div>
            )}

            <div style={{
              background: '#ffebee',
              border: '2px solid #f44336',
              borderRadius: '8px',
              padding: '1rem',
              marginTop: '1rem'
            }}>
              {!showConfirmResign ? (
                <>
                  <button
                    style={{
                      width: '100%',
                      padding: '1rem',
                      background: loading ? '#ccc' : '#f44336',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '1rem',
                      fontWeight: 'bold',
                      cursor: loading ? 'not-allowed' : 'pointer',
                      marginBottom: '0.5rem'
                    }}
                    onClick={handleResignClick}
                    disabled={loading}
                  >
                    Resign from Game
                  </button>
                  <p style={{ margin: 0, fontSize: '0.9rem', color: '#c62828', textAlign: 'center' }}>
                    All assets will be forfeited and returned to the bank
                  </p>
                </>
              ) : (
                <>
                  <p style={{ margin: '0 0 1rem 0', color: '#c62828', fontWeight: 'bold' }}>
                    Are you sure? This action cannot be undone. All your properties, improvements,
                    and cash will be forfeited to the bank.
                  </p>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      style={{
                        flex: 1,
                        padding: '1rem',
                        background: loading ? '#ccc' : '#f44336',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '8px',
                        fontSize: '1rem',
                        fontWeight: 'bold',
                        cursor: loading ? 'not-allowed' : 'pointer'
                      }}
                      onClick={handleConfirmResign}
                      disabled={loading}
                    >
                      {loading ? 'Resigning...' : 'Yes, Resign'}
                    </button>
                    <button
                      style={{
                        flex: 1,
                        padding: '1rem',
                        background: loading ? '#ccc' : '#757575',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '8px',
                        fontSize: '1rem',
                        fontWeight: 'bold',
                        cursor: loading ? 'not-allowed' : 'pointer'
                      }}
                      onClick={() => setShowConfirmResign(false)}
                      disabled={loading}
                    >
                      Cancel
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
