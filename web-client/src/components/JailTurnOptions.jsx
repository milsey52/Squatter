import { useState, useEffect } from 'react';

const API_BASE = (import.meta.env.VITE_API_BASE !== undefined && import.meta.env.VITE_API_BASE !== '')
  ? import.meta.env.VITE_API_BASE
  : window.location.origin;

export default function JailTurnOptions({ gameId, sessionToken, onAction }) {
  const [jailStatus, setJailStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchJailStatus = async () => {
      try {
        const response = await fetch(`${API_BASE}/games/${gameId}/turns/jail/status`, {
          headers: {
            'Authorization': `Bearer ${sessionToken}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          setJailStatus(data);
        }
      } catch (err) {
        console.error('Error fetching jail status:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchJailStatus();
  }, [gameId, sessionToken]);

  const handlePayFine = async () => {
    setProcessing(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/turns/jail/pay-fine`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to pay fine');
      }

      // Success - notify parent to refresh and close modal
      if (onAction) onAction();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleUseCard = async () => {
    setProcessing(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/turns/jail/use-card`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to use card');
      }

      // Success - notify parent to refresh and close modal
      if (onAction) onAction();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleRollDice = () => {
    console.log('[JailTurnOptions] Roll Doubles clicked, processing:', processing);
    // Just close the modal and let them roll normally
    if (onAction) onAction();
  };

  if (loading) {
    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000
      }}>
        <div style={{
          background: 'white',
          padding: '2rem',
          borderRadius: '12px',
          textAlign: 'center'
        }}>
          Loading jail status...
        </div>
      </div>
    );
  }

  if (!jailStatus || !jailStatus.in_jail) {
    return null;
  }

  console.log('[JailTurnOptions] Rendering, processing:', processing, 'jailStatus:', jailStatus);

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 10001
    }}>
      <div style={{
        background: 'white',
        padding: '2.5rem',
        borderRadius: '16px',
        maxWidth: '550px',
        boxShadow: '0 10px 40px rgba(0,0,0,0.3)'
      }}>
        <div style={{
          textAlign: 'center',
          marginBottom: '2rem'
        }}>
          <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>🔒</div>
          <h2 style={{
            margin: '0 0 0.5rem 0',
            color: '#d32f2f',
            fontSize: '2rem'
          }}>
            You're in Jail!
          </h2>
          <p style={{
            fontSize: '1.1rem',
            color: '#666',
            margin: '0'
          }}>
            Turn {jailStatus.jail_turns} of 3 • {jailStatus.turns_remaining} attempts remaining
          </p>
        </div>

        <div style={{
          background: '#f5f5f5',
          padding: '1.5rem',
          borderRadius: '12px',
          marginBottom: '2rem'
        }}>
          <p style={{
            margin: '0 0 1rem 0',
            fontWeight: 'bold',
            fontSize: '1.1rem',
            color: '#333'
          }}>
            Choose your action:
          </p>

          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem'
          }}>
            {/* Pay Fine Option */}
            <button
              onClick={handlePayFine}
              disabled={processing || !jailStatus.can_afford_fine}
              style={{
                padding: '1.25rem',
                background: jailStatus.can_afford_fine ? '#28a745' : '#ccc',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '1.1rem',
                fontWeight: 'bold',
                cursor: jailStatus.can_afford_fine && !processing ? 'pointer' : 'not-allowed',
                textAlign: 'left',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                opacity: processing ? 0.6 : 1
              }}
            >
              <span>💰 Pay ${jailStatus.jail_fine} Fine</span>
              {!jailStatus.can_afford_fine && (
                <span style={{ fontSize: '0.9rem', opacity: 0.8 }}>
                  (Need ${jailStatus.jail_fine - jailStatus.balance} more)
                </span>
              )}
            </button>

            {/* Use Card Option */}
            {jailStatus.has_jail_card && (
              <button
                onClick={handleUseCard}
                disabled={processing}
                style={{
                  padding: '1.25rem',
                  background: '#ffc107',
                  color: '#000',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '1.1rem',
                  fontWeight: 'bold',
                  cursor: processing ? 'not-allowed' : 'pointer',
                  textAlign: 'left',
                  opacity: processing ? 0.6 : 1
                }}
              >
                🎫 Use "Get Out of Jail Free" Card
              </button>
            )}

            {/* Roll Doubles Option */}
            <button
              onClick={handleRollDice}
              disabled={processing}
              style={{
                padding: '1.25rem',
                background: '#1982c4',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '1.1rem',
                fontWeight: 'bold',
                cursor: processing ? 'not-allowed' : 'pointer',
                textAlign: 'left',
                opacity: processing ? 0.6 : 1
              }}
            >
              🎲 Try to Roll Doubles (Free)
            </button>
          </div>
        </div>

        {error && (
          <div style={{
            background: '#ffebee',
            color: '#c62828',
            padding: '1rem',
            borderRadius: '8px',
            marginBottom: '1rem',
            textAlign: 'center'
          }}>
            {error}
          </div>
        )}

        <div style={{
          fontSize: '0.9rem',
          color: '#888',
          textAlign: 'center',
          fontStyle: 'italic'
        }}>
          {jailStatus.turns_remaining === 1 ? (
            <strong style={{ color: '#d32f2f' }}>
              ⚠️ Last chance! If you don't roll doubles, you'll automatically pay ${jailStatus.jail_fine}.
            </strong>
          ) : (
            `If you don't roll doubles in ${jailStatus.turns_remaining} turn${jailStatus.turns_remaining > 1 ? 's' : ''}, you'll automatically pay the fine.`
          )}
        </div>
      </div>
    </div>
  );
}
