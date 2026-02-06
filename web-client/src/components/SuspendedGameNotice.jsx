import { useState, useEffect, useCallback } from 'react';
import { Z_INDEX } from '../constants/zIndex';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function SuspendedGameNotice({ gameId, sessionToken }) {
  const [playerStatus, setPlayerStatus] = useState(null);

  const fetchPlayerStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/player-status`, {
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setPlayerStatus(data);
      }
    } catch (error) {
      console.error('Error fetching player status:', error);
    }
  }, [gameId, sessionToken]);

  useEffect(() => {
    fetchPlayerStatus();

    // Poll every 3 seconds
    const interval = setInterval(fetchPlayerStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchPlayerStatus]);

  if (!playerStatus) {
    return null;
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.85)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: Z_INDEX.MODAL_SUSPENDED
    }}>
      <div style={{
        background: 'white',
        borderRadius: '16px',
        padding: '3rem',
        maxWidth: '500px',
        textAlign: 'center',
        boxShadow: '0 10px 40px rgba(0,0,0,0.3)'
      }}>
        <div style={{
          fontSize: '4rem',
          marginBottom: '1rem'
        }}>
          ⏸️
        </div>
        <h2 style={{
          margin: '0 0 1rem 0',
          color: '#ff6b6b',
          fontSize: '2rem'
        }}>
          Game Suspended
        </h2>
        <p style={{
          fontSize: '1.1rem',
          color: '#555',
          marginBottom: '2rem'
        }}>
          Waiting for all players to return...
        </p>

        <div style={{
          background: '#f8f9fa',
          borderRadius: '12px',
          padding: '1.5rem',
          marginBottom: '1.5rem'
        }}>
          <h3 style={{
            margin: '0 0 1rem 0',
            fontSize: '1.1rem',
            color: '#333'
          }}>
            Player Status:
          </h3>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem'
          }}>
            {playerStatus.players.map(p => (
              <div key={p.game_player_id} style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.75rem',
                background: p.logged_in ? '#d4edda' : '#f8d7da',
                border: `2px solid ${p.logged_in ? '#28a745' : '#dc3545'}`,
                borderRadius: '8px'
              }}>
                <span style={{
                  fontWeight: 'bold',
                  color: '#333'
                }}>
                  {p.player_name}
                </span>
                <span style={{
                  color: p.logged_in ? '#28a745' : '#dc3545',
                  fontWeight: 'bold'
                }}>
                  {p.logged_in ? '✓ Online' : '✗ Offline'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div style={{
          fontSize: '0.9rem',
          color: '#888',
          fontStyle: 'italic'
        }}>
          The game will automatically resume when all players are back.
        </div>
      </div>
    </div>
  );
}
