import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function GameSelector({ onGameJoined }) {
  const [mode, setMode] = useState('select'); // 'select', 'create', 'join'
  const [playerName, setPlayerName] = useState('');
  const [gameCode, setGameCode] = useState('');
  const [maxPlayers, setMaxPlayers] = useState(6);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Check for game code in URL params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    if (code) {
      setGameCode(code.toUpperCase());
      setMode('join');
    }
  }, []);

  const createGame = async (e) => {
    e.preventDefault();
    if (!playerName.trim()) {
      setError('Please enter your name');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/games/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host_user_name: playerName.trim(),
          max_players: maxPlayers
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create game');
      }

      const data = await response.json();

      // Store session token
      localStorage.setItem('squatter_session_token', data.session_token);
      localStorage.setItem('squatter_player_name', playerName.trim());

      // Notify parent component
      onGameJoined({
        gameId: data.game_id,
        gameCode: data.game_code,
        sessionToken: data.session_token,
        userId: data.host_user_id,
        playerName: playerName.trim(),
        isHost: true
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const joinGame = async (e) => {
    e.preventDefault();
    if (!playerName.trim()) {
      setError('Please enter your name');
      return;
    }
    if (!gameCode.trim() || gameCode.trim().length !== 6) {
      setError('Please enter a valid 6-character game code');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/games/join/${gameCode.trim().toUpperCase()}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_name: playerName.trim()
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to join game');
      }

      const data = await response.json();

      // Store session token
      localStorage.setItem('squatter_session_token', data.session_token);
      localStorage.setItem('squatter_player_name', playerName.trim());

      // Notify parent component
      onGameJoined({
        gameId: data.game_id,
        gameCode: data.game_code,
        sessionToken: data.session_token,
        userId: data.user_id,
        playerName: playerName.trim(),
        isHost: false,
        gameStatus: data.status
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (mode === 'select') {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #2d5016 0%, #4a7c23 100%)',
        fontFamily: 'sans-serif'
      }}>
        <div style={{
          background: '#fff',
          padding: '3rem',
          borderRadius: '16px',
          boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
          maxWidth: '400px',
          width: '90%'
        }}>
          <h1 style={{ margin: '0 0 1rem 0', textAlign: 'center', color: '#333' }}>
            Squatter
          </h1>
          <p style={{ textAlign: 'center', color: '#666', marginBottom: '2rem' }}>
            The Australian Sheep Station Game
          </p>

          <button
            onClick={() => setMode('create')}
            style={{
              width: '100%',
              padding: '1rem',
              marginBottom: '1rem',
              background: '#1982c4',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '1.1rem',
              fontWeight: 'bold',
              cursor: 'pointer',
              transition: 'background 0.2s'
            }}
            onMouseOver={(e) => e.target.style.background = '#1565a0'}
            onMouseOut={(e) => e.target.style.background = '#1982c4'}
          >
            Create New Game
          </button>

          <button
            onClick={() => setMode('join')}
            style={{
              width: '100%',
              padding: '1rem',
              background: '#6a4c93',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '1.1rem',
              fontWeight: 'bold',
              cursor: 'pointer',
              transition: 'background 0.2s'
            }}
            onMouseOver={(e) => e.target.style.background = '#553a73'}
            onMouseOut={(e) => e.target.style.background = '#6a4c93'}
          >
            Join Existing Game
          </button>
        </div>
      </div>
    );
  }

  if (mode === 'create') {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #2d5016 0%, #4a7c23 100%)',
        fontFamily: 'sans-serif'
      }}>
        <div style={{
          background: '#fff',
          padding: '3rem',
          borderRadius: '16px',
          boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
          maxWidth: '400px',
          width: '90%'
        }}>
          <h2 style={{ margin: '0 0 1.5rem 0', textAlign: 'center', color: '#333' }}>
            Create New Game
          </h2>

          <form onSubmit={createGame}>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: '#555', fontWeight: '500' }}>
                Your Name
              </label>
              <input
                type="text"
                value={playerName}
                onChange={(e) => setPlayerName(e.target.value)}
                placeholder="Enter your name"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '2px solid #e0e0e0',
                  borderRadius: '8px',
                  fontSize: '1rem',
                  boxSizing: 'border-box'
                }}
                autoFocus
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: '#555', fontWeight: '500' }}>
                Max Players
              </label>
              <select
                value={maxPlayers}
                onChange={(e) => setMaxPlayers(parseInt(e.target.value))}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '2px solid #e0e0e0',
                  borderRadius: '8px',
                  fontSize: '1rem',
                  boxSizing: 'border-box'
                }}
              >
                <option value={2}>2 Players</option>
                <option value={3}>3 Players</option>
                <option value={4}>4 Players</option>
                <option value={5}>5 Players</option>
                <option value={6}>6 Players</option>
              </select>
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

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '1rem',
                marginBottom: '0.75rem',
                background: loading ? '#ccc' : '#1982c4',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '1.1rem',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
            >
              {loading ? 'Creating...' : 'Create Game'}
            </button>

            <button
              type="button"
              onClick={() => { setMode('select'); setError(''); }}
              style={{
                width: '100%',
                padding: '0.75rem',
                background: 'transparent',
                color: '#666',
                border: '2px solid #e0e0e0',
                borderRadius: '8px',
                fontSize: '1rem',
                cursor: 'pointer'
              }}
            >
              Back
            </button>
          </form>
        </div>
      </div>
    );
  }

  if (mode === 'join') {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #2d5016 0%, #4a7c23 100%)',
        fontFamily: 'sans-serif'
      }}>
        <div style={{
          background: '#fff',
          padding: '3rem',
          borderRadius: '16px',
          boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
          maxWidth: '400px',
          width: '90%'
        }}>
          <h2 style={{ margin: '0 0 1.5rem 0', textAlign: 'center', color: '#333' }}>
            Join Game
          </h2>

          <form onSubmit={joinGame}>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: '#555', fontWeight: '500' }}>
                Your Name
              </label>
              <input
                type="text"
                value={playerName}
                onChange={(e) => setPlayerName(e.target.value)}
                placeholder="Enter your name"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '2px solid #e0e0e0',
                  borderRadius: '8px',
                  fontSize: '1rem',
                  boxSizing: 'border-box'
                }}
                autoFocus={!gameCode}
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: '#555', fontWeight: '500' }}>
                Game Code
              </label>
              <input
                type="text"
                value={gameCode}
                onChange={(e) => setGameCode(e.target.value.toUpperCase())}
                placeholder="e.g. ABCD12"
                maxLength={6}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '2px solid #e0e0e0',
                  borderRadius: '8px',
                  fontSize: '1.2rem',
                  fontWeight: 'bold',
                  letterSpacing: '2px',
                  textAlign: 'center',
                  textTransform: 'uppercase',
                  boxSizing: 'border-box'
                }}
                autoFocus={!!gameCode}
              />
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

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '1rem',
                marginBottom: '0.75rem',
                background: loading ? '#ccc' : '#6a4c93',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '1.1rem',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
            >
              {loading ? 'Joining...' : 'Join Game'}
            </button>

            <button
              type="button"
              onClick={() => { setMode('select'); setError(''); setGameCode(''); }}
              style={{
                width: '100%',
                padding: '0.75rem',
                background: 'transparent',
                color: '#666',
                border: '2px solid #e0e0e0',
                borderRadius: '8px',
                fontSize: '1rem',
                cursor: 'pointer'
              }}
            >
              Back
            </button>
          </form>
        </div>
      </div>
    );
  }
}
