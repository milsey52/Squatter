import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function TurnOrderRoll({ gameId, sessionToken, userId, isHost, onComplete }) {
  const [rolls, setRolls] = useState([]);
  const [winner, setWinner] = useState(null);
  const [needsReroll, setNeedsReroll] = useState(false);
  const [tiedPlayers, setTiedPlayers] = useState([]);
  const [allRolled, setAllRolled] = useState(false);
  const [currentRound, setCurrentRound] = useState(1);
  const [rolling, setRolling] = useState(false);

  const fetchRolls = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/turn-order/rolls`, {
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        console.error('Failed to fetch rolls:', response.status);
        return;
      }

      const data = await response.json();
      setRolls(data.rolls || []);
      setWinner(data.winner);
      setNeedsReroll(data.needs_reroll);
      setTiedPlayers(data.tied_players || []);
      setAllRolled(data.all_rolled);
      setCurrentRound(data.round);
    } catch (error) {
      console.error('Error fetching rolls:', error);
    }
  }, [gameId, sessionToken]);

  useEffect(() => {
    fetchRolls();

    // Poll every 2 seconds for updates
    const interval = setInterval(fetchRolls, 2000);
    return () => clearInterval(interval);
  }, [fetchRolls]);

  const handleRoll = async () => {
    setRolling(true);
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/turn-order/roll`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        const error = await response.json();
        alert(error.detail || 'Failed to roll dice');
        return;
      }

      // Fetch updated rolls
      await fetchRolls();
    } catch (error) {
      console.error('Error rolling dice:', error);
      alert('Failed to roll dice');
    } finally {
      setRolling(false);
    }
  };

  const handleReroll = async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/turn-order/start-reroll`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        const error = await response.json();
        alert(error.detail || 'Failed to start reroll');
        return;
      }

      // Fetch updated rolls
      await fetchRolls();
    } catch (error) {
      console.error('Error starting reroll:', error);
      alert('Failed to start reroll');
    }
  };

  const handleContinue = async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/turn-order/finalize`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        const error = await response.json();
        alert(error.detail || 'Failed to finalize turn order');
        return;
      }

      const data = await response.json();
      // Call onComplete callback to close modal and start game
      if (onComplete) {
        onComplete();
      }
    } catch (error) {
      console.error('Error finalizing turn order:', error);
      alert('Failed to finalize turn order');
    }
  };

  // Check if current user has rolled
  const userHasRolled = rolls.some(r => r.player_name);

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
        borderRadius: '12px',
        padding: '2rem',
        minWidth: '500px',
        maxWidth: '600px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.3)'
      }}>
        <h2 style={{
          margin: '0 0 1.5rem 0',
          color: '#1982c4',
          textAlign: 'center',
          fontSize: '1.8rem'
        }}>
          🎲 Roll for Turn Order
        </h2>

        {currentRound > 1 && (
          <div style={{
            background: '#fff3cd',
            border: '2px solid #ffc107',
            borderRadius: '8px',
            padding: '0.75rem',
            marginBottom: '1rem',
            textAlign: 'center',
            fontWeight: 'bold',
            color: '#856404'
          }}>
            Round {currentRound} - Reroll for tied players
          </div>
        )}

        <div style={{
          marginBottom: '1.5rem'
        }}>
          {rolls.map((roll, index) => (
            <div key={roll.game_player_id} style={{
              display: 'flex',
              alignItems: 'center',
              padding: '0.75rem',
              marginBottom: '0.5rem',
              background: '#f8f9fa',
              borderRadius: '8px',
              border: '2px solid #e0e0e0'
            }}>
              <div style={{
                flex: 1,
                fontWeight: 'bold',
                fontSize: '1.1rem',
                color: '#333'
              }}>
                {roll.player_name}
              </div>
              <div style={{
                flex: 1,
                textAlign: 'center',
                fontSize: '1.1rem',
                color: '#1982c4',
                fontWeight: 'bold'
              }}>
                {roll.dice1 && roll.dice2 ? (
                  `${roll.dice1} + ${roll.dice2} = ${roll.total}`
                ) : roll.user_id === userId ? (
                  <button
                    onClick={handleRoll}
                    disabled={rolling}
                    style={{
                      padding: '0.5rem 1.5rem',
                      background: '#1982c4',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      fontSize: '1rem',
                      fontWeight: 'bold',
                      cursor: rolling ? 'not-allowed' : 'pointer',
                      opacity: rolling ? 0.6 : 1
                    }}
                  >
                    {rolling ? 'Rolling...' : 'Roll Dice'}
                  </button>
                ) : (
                  <span style={{ color: '#999', fontStyle: 'italic' }}>
                    Waiting...
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        {allRolled && needsReroll && (
          <div style={{
            background: '#fff3cd',
            border: '2px solid #ffc107',
            borderRadius: '8px',
            padding: '1rem',
            marginBottom: '1rem',
            textAlign: 'center'
          }}>
            <strong style={{ color: '#856404' }}>Tie!</strong>
            <div style={{ marginTop: '0.5rem', color: '#856404' }}>
              {tiedPlayers.map(p => p.player_name).join(' and ')} tied with {tiedPlayers[0]?.total}
            </div>
            {isHost && (
              <button
                onClick={handleReroll}
                style={{
                  marginTop: '1rem',
                  padding: '0.75rem 2rem',
                  background: '#ffc107',
                  color: '#000',
                  border: 'none',
                  borderRadius: '6px',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                Start Reroll
              </button>
            )}
          </div>
        )}

        {winner && (
          <div style={{
            background: 'linear-gradient(135deg, #28a745 0%, #20c997 100%)',
            border: '3px solid #20c997',
            borderRadius: '12px',
            padding: '1.5rem',
            marginTop: '1.5rem',
            textAlign: 'center',
            color: 'white'
          }}>
            <div style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>
              🏆 Winner
            </div>
            <div style={{ fontSize: '2rem', fontWeight: 'bold' }}>
              {winner.player_name}
            </div>
            <div style={{ fontSize: '1.1rem', marginTop: '0.5rem', opacity: 0.9 }}>
              Rolled {winner.total} - Goes First!
            </div>
          </div>
        )}

        {isHost && winner && (
          <div style={{
            marginTop: '1.5rem',
            textAlign: 'center'
          }}>
            <button
              onClick={handleContinue}
              style={{
                padding: '1rem 3rem',
                background: '#1982c4',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '1.2rem',
                fontWeight: 'bold',
                cursor: 'pointer',
                boxShadow: '0 4px 8px rgba(0,0,0,0.2)'
              }}
              onMouseEnter={(e) => e.target.style.background = '#1569a0'}
              onMouseLeave={(e) => e.target.style.background = '#1982c4'}
            >
              Continue to Game
            </button>
          </div>
        )}

        {!isHost && !winner && allRolled && !needsReroll && (
          <div style={{
            textAlign: 'center',
            color: '#666',
            fontStyle: 'italic',
            marginTop: '1rem'
          }}>
            Waiting for host to continue...
          </div>
        )}
      </div>
    </div>
  );
}
