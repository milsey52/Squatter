import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export default function GameLobby({ gameId, gameCode, sessionToken, userId, isHost, onGameStarted }) {
  const [lobbyData, setLobbyData] = useState(null);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    fetchLobbyStatus();
    // Poll for lobby updates every 2 seconds
    const interval = setInterval(fetchLobbyStatus, 2000);
    return () => clearInterval(interval);
  }, [gameId, sessionToken]);

  const fetchLobbyStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/lobby`, {
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch lobby status');
      }

      const data = await response.json();
      setLobbyData(data);

      // Update local ready status
      const currentPlayer = data.players.find(p => p.user_id === userId);
      if (currentPlayer) {
        setIsReady(currentPlayer.is_ready);
      }

      // If game has started, notify parent
      if (data.status === 'in_progress') {
        onGameStarted();
      }

      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const toggleReady = async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/lobby/ready`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ ready: !isReady })
      });

      if (!response.ok) {
        throw new Error('Failed to update ready status');
      }

      const data = await response.json();
      setIsReady(data.is_ready);
      fetchLobbyStatus(); // Refresh to show updated status
    } catch (err) {
      setError(err.message);
    }
  };

  const startGame = async () => {
    setStarting(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/lobby/start`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to start game');
      }

      // Game started - parent component will handle transition
      onGameStarted();
    } catch (err) {
      setError(err.message);
      setStarting(false);
    }
  };

  const copyGameCode = () => {
    navigator.clipboard.writeText(gameCode);
    // Could add a toast notification here
  };

  const copyLink = () => {
    const url = `${window.location.origin}${window.location.pathname}?code=${gameCode}`;
    navigator.clipboard.writeText(url);
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        fontFamily: 'sans-serif'
      }}>
        <div>Loading lobby...</div>
      </div>
    );
  }

  if (!lobbyData) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        fontFamily: 'sans-serif'
      }}>
        <div style={{ color: '#c33' }}>{error || 'Failed to load lobby'}</div>
      </div>
    );
  }

  const allReady = lobbyData.players.every(p => p.is_ready);
  const canStart = isHost && allReady && lobbyData.players.length >= 2;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      fontFamily: 'sans-serif',
      padding: '2rem'
    }}>
      <div style={{
        background: '#fff',
        padding: '2.5rem',
        borderRadius: '16px',
        boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
        maxWidth: '600px',
        width: '100%'
      }}>
        <h1 style={{ margin: '0 0 0.5rem 0', textAlign: 'center', color: '#333' }}>
          Game Lobby
        </h1>

        {/* Game Code Display */}
        <div style={{
          background: 'linear-gradient(135deg, #1982c4 0%, #1565a0 100%)',
          padding: '1.5rem',
          borderRadius: '12px',
          marginBottom: '2rem',
          textAlign: 'center'
        }}>
          <div style={{ color: 'rgba(255,255,255,0.9)', marginBottom: '0.5rem', fontSize: '0.9rem' }}>
            Game Code
          </div>
          <div style={{
            fontSize: '2.5rem',
            fontWeight: 'bold',
            color: '#fff',
            letterSpacing: '8px',
            marginBottom: '1rem'
          }}>
            {gameCode}
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
            <button
              onClick={copyGameCode}
              style={{
                padding: '0.5rem 1.25rem',
                background: 'rgba(255,255,255,0.2)',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.3)',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '0.9rem',
                fontWeight: '500'
              }}
            >
              📋 Copy Code
            </button>
            <button
              onClick={copyLink}
              style={{
                padding: '0.5rem 1.25rem',
                background: 'rgba(255,255,255,0.2)',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.3)',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '0.9rem',
                fontWeight: '500'
              }}
            >
              🔗 Copy Link
            </button>
          </div>
          <div style={{ color: 'rgba(255,255,255,0.8)', marginTop: '0.75rem', fontSize: '0.85rem' }}>
            Share this code with friends to invite them!
          </div>
        </div>

        {/* Players List */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1rem 0', color: '#555' }}>
            Players ({lobbyData.players.length}/{lobbyData.max_players})
          </h3>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {lobbyData.players.map((player) => (
              <li
                key={player.user_id}
                style={{
                  padding: '1rem',
                  marginBottom: '0.75rem',
                  background: player.is_ready ? '#e8f5e9' : '#f5f5f5',
                  border: `2px solid ${player.is_ready ? '#4caf50' : '#e0e0e0'}`,
                  borderRadius: '8px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <div>
                  <strong style={{ fontSize: '1.05rem' }}>
                    {player.player_name}
                    {player.user_id === lobbyData.host_user_id && (
                      <span style={{
                        marginLeft: '0.5rem',
                        padding: '2px 8px',
                        background: '#ff924c',
                        color: '#fff',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 'bold'
                      }}>
                        HOST
                      </span>
                    )}
                  </strong>
                </div>
                <div>
                  {player.is_ready ? (
                    <span style={{ color: '#4caf50', fontWeight: 'bold' }}>✓ Ready</span>
                  ) : (
                    <span style={{ color: '#999' }}>Not Ready</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>

        {error && (
          <div style={{
            padding: '0.75rem',
            marginBottom: '1rem',
            background: '#fee',
            border: '1px solid #fcc',
            borderRadius: '6px',
            color: '#c33',
            fontSize: '0.9rem'
          }}>
            {error}
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={toggleReady}
            style={{
              flex: 1,
              padding: '1rem',
              background: isReady ? '#999' : '#4caf50',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '1rem',
              fontWeight: 'bold',
              cursor: 'pointer'
            }}
          >
            {isReady ? 'Not Ready' : 'Ready'}
          </button>

          {isHost && (
            <button
              onClick={startGame}
              disabled={!canStart || starting}
              style={{
                flex: 1,
                padding: '1rem',
                background: canStart && !starting ? '#1982c4' : '#ccc',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '1rem',
                fontWeight: 'bold',
                cursor: canStart && !starting ? 'pointer' : 'not-allowed'
              }}
            >
              {starting ? 'Starting...' : 'Start Game'}
            </button>
          )}
        </div>

        {isHost && !canStart && (
          <div style={{
            marginTop: '1rem',
            padding: '0.75rem',
            background: '#fff3cd',
            border: '1px solid #ffc107',
            borderRadius: '6px',
            color: '#856404',
            fontSize: '0.85rem',
            textAlign: 'center'
          }}>
            {lobbyData.players.length < 2
              ? 'Waiting for more players to join...'
              : 'Waiting for all players to be ready...'
            }
          </div>
        )}
      </div>
    </div>
  );
}
