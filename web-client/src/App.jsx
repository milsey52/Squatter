import { useEffect, useState, useCallback } from "react";
import Board from "./Board";
import PurchaseModal from "./PurchaseModal";
import AuctionModal from "./AuctionModal";
import GameSelector from "./components/GameSelector";
import GameLobby from "./components/GameLobby";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";                                                                                                             
const SPACE_LABELS = [                                                                                                                                                                 
  "Start/Payday",                                                                                                                                                                      
  "Belvue House",                                                                                                                                                                      
  "Balga Inn",                                                                                                                                                                         
  "Welfare Centre",                                                                                                                                                                    
  "Income Tax",                                                                                                                                                                        
  "Transperth",                                                                                                                                                                        
  "Ascot Waters",                                                                                                                                                                      
  "Midland",                                                                                                                                                                           
  "Chance",                                                                                                                                                                            
  "Swan Vineyard",                                                                                                                                                                     
  "Visit Jail",                                                                                                                                                                        
  "Optus Stadium",                                                                                                                                                                     
  "Synergy",                                                                                                                                                                           
  "WACA",                                                                                                                                                                              
  "Perth Arena",                                                                                                                                                                       
  "Warwick Train Station",                                                                                                                                                             
  "Hillarys Boat Harbour",                                                                                                                                                             
  "Water World",                                                                                                                                                                       
  "Adventure World",                                                                                                                                                                   
  "Welfare Centre",                                                                                                                                                                    
  "Salvo Rest Home",                                                                                                                                                                   
  "Whitfords Shopping Centre",                                                                                                                                                         
  "Cannington Shopping Centre",                                                                                                                                                        
  "Chance",                                                                                                                                                                            
  "Carrillon City",                                                                                                                                                                    
  "Rottnest Express",                                                                                                                                                                  
  "Rottnest Island",                                                                                                                                                                   
  "Alinta Gas",                                                                                                                                                                        
  "City Beach",                                                                                                                                                                        
  "Yanchep Beach",                                                                                                                                                                     
  "Police Arrest – Imprisonment",                                                                                                                                                      
  "Perth Zoo",                                                                                                                                                                         
  "Welfare Centre",                                                                                                                                                                    
  "Curtin Uni",                                                                                                                                                                        
  "The Casino",                                                                                                                                                                        
  "Perth Airport",                                                                                                                                                                     
  "Chance",                                                                                                                                                                            
  "Nedlands",                                                                                                                                                                          
  "Mortgage Payment",                                                                                                                                                                  
  "Kings Park",                                                                                                                                                                        
];                                                                                                                                                                                     
                                                                                                                                                                                       
function App() {
  // Routing and session state
  const [screen, setScreen] = useState('selector'); // 'selector', 'lobby', 'game'
  const [gameId, setGameId] = useState(null);
  const [gameCode, setGameCode] = useState(null);
  const [sessionToken, setSessionToken] = useState(localStorage.getItem('monopoly_session_token'));
  const [userId, setUserId] = useState(null);
  const [isHost, setIsHost] = useState(false);

  // Game state
  const [game, setGame] = useState(null);                                                                                                                                              
  const [ledger, setLedger] = useState([]);                                                                                                                                            
  const [jackpot, setJackpot] = useState(null);                                                                                                                                        
  const [playerBalances, setPlayerBalances] = useState({});                                                                                                                            
  const [allPlayerAssets, setAllPlayerAssets] = useState({});                                                                                                                          
  const [loading, setLoading] = useState(true);                                                                                                                                        
  const [error, setError] = useState(null);                                                                                                                                            
  const [isSubmitting, setIsSubmitting] = useState(false);                                                                                                                             
  const [playerRetainedCards, setPlayerRetainedCards] = useState({});
  const [lastDrawnCards, setLastDrawnCards] = useState({ CHANCE: null, WELFARE: null });
  const [lastDiceRoll, setLastDiceRoll] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [showTradingBoard, setShowTradingBoard] = useState(false);
  const [tradingBoardPos, setTradingBoardPos] = useState({ x: 200, y: 200 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  // Handle game joined from selector
  const handleGameJoined = (data) => {
    setGameId(data.gameId);
    setGameCode(data.gameCode);
    setSessionToken(data.sessionToken);
    setUserId(data.userId);
    setIsHost(data.isHost);

    // Save session token to localStorage
    localStorage.setItem('monopoly_session_token', data.sessionToken);

    // If game already in progress, go straight to game
    if (data.gameStatus === 'in_progress') {
      setScreen('game');
    } else {
      setScreen('lobby');
    }
  };

  // Handle game started from lobby
  const handleGameStarted = () => {
    setScreen('game');
  };

  // Check for existing session on mount
  useEffect(() => {
    const token = localStorage.getItem('monopoly_session_token');
    if (token) {
      // Validate session token with API
      fetch(`${API_BASE}/games/session/validate`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
        .then(res => {
          if (!res.ok) throw new Error('Invalid session');
          return res.json();
        })
        .then(data => {
          // Restore session state
          setSessionToken(token);
          setGameId(data.game_id);
          setGameCode(data.game_code);
          setUserId(data.user_id);
          setIsHost(data.is_host);

          // Navigate to appropriate screen
          if (data.game_status === 'lobby') {
            setScreen('lobby');
          } else if (data.game_status === 'in_progress') {
            setScreen('game');
          } else {
            // Game ended or invalid status
            localStorage.removeItem('monopoly_session_token');
            setScreen('selector');
          }
        })
        .catch(() => {
          // Invalid or expired token
          localStorage.removeItem('monopoly_session_token');
          setScreen('selector');
        });
    } else {
      setScreen('selector');
    }
  }, []);

  const fetchGameLedgerJackpot = useCallback(async () => {
    if (!gameId) return;

    const headers = sessionToken ? {
      'Authorization': `Bearer ${sessionToken}`
    } : {};

    const [gameRes, ledgerRes, jackpotRes, balancesRes, assetsRes, cardsRes, lastDrawnCardsRes, pendingRes] = await Promise.all([
      fetch(`${API_BASE}/games/${gameId}`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/ledger`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/jackpot`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/player_balances`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/player_assets`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/player_retained_cards`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/last_drawn_cards`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/pending-action`, { headers })
    ]);                                                                                                                                                                                
                                                       
    
    if (!gameRes.ok) {                                                                                                                                                                 
      const text = await gameRes.text();                                                                                                                                               
      throw new Error(`Failed to load game: ${gameRes.status}`);                                                                                                                       
    }                                                                                                                                                                                  
                                                                                                                                                                                       
    if (!ledgerRes.ok) {                                                                                                                                                               
      const text = await ledgerRes.text();                                                                                                                                             
      throw new Error(`Failed to load ledger: ${ledgerRes.status}`);                                                                                                                   
    }                                                                                                                                                                                  
                                                                                                                                                                                       
    const gameData = await gameRes.json();
    const ledgerData = await ledgerRes.json();
    const jackpotData = jackpotRes.ok ? await jackpotRes.json() : { jackpot: null };
    const balancesData = balancesRes.ok ? await balancesRes.json() : {};
    const assetsData = assetsRes.ok ? await assetsRes.json() : {};
    const cardsData = cardsRes.ok ? await cardsRes.json() : {};
    const lastDrawnCardsData = lastDrawnCardsRes.ok ? await lastDrawnCardsRes.json() : { CHANCE: null, WELFARE: null };
    const pendingData = pendingRes.ok ? await pendingRes.json() : { pending_action: null };

    setGame(gameData);
    setLedger(Array.isArray(ledgerData) ? ledgerData : []);
    setJackpot(jackpotData.jackpot);
    setPlayerBalances(balancesData);
    setAllPlayerAssets(assetsData);
    setPlayerRetainedCards(cardsData);
    setLastDrawnCards(lastDrawnCardsData);
    setPendingAction(pendingData.pending_action);
    setError(null);
  }, [gameId, sessionToken]);

  // Only fetch game data when on the game screen
  useEffect(() => {
    if (screen !== 'game' || !gameId) return;

    setLoading(true);
    fetchGameLedgerJackpot()
      .catch((err) => {
        setError(err.message);
        setGame(null);
        setLedger([]);
        setJackpot(null);
        setAllPlayerAssets({});
        setPlayerRetainedCards({});
        setLastDrawnCards({ CHANCE: null, WELFARE: null });
        setPendingAction(null);
      })
      .finally(() => setLoading(false));
  }, [screen, gameId, fetchGameLedgerJackpot]);

  // Keyboard shortcut for trading board (Ctrl+T or Cmd+T)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 't') {
        e.preventDefault();
        setShowTradingBoard(prev => !prev);
      }
      // ESC to close trading board
      if (e.key === 'Escape' && showTradingBoard) {
        setShowTradingBoard(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showTradingBoard]);

  // Trading board drag handlers
  const handleTradingBoardMouseDown = (e) => {
    if (e.target.classList.contains('trading-board-header')) {
      setIsDragging(true);
      setDragOffset({
        x: e.clientX - tradingBoardPos.x,
        y: e.clientY - tradingBoardPos.y
      });
    }
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (isDragging) {
        setTradingBoardPos({
          x: e.clientX - dragOffset.x,
          y: e.clientY - dragOffset.y
        });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragOffset]);

  const nextTurn = async () => {
    if (isSubmitting) return;

    setIsSubmitting(true);
    try {
      const headers = sessionToken ? {
        'Authorization': `Bearer ${sessionToken}`
      } : {};

      const response = await fetch(`${API_BASE}/games/${gameId}/turns`, {
        method: "POST",
        headers
      });
      if (!response.ok) {
        throw new Error(`Failed to execute turn: ${response.status}`);
      }
      const turnData = await response.json();
      setLastDiceRoll(turnData);
      await fetchGameLedgerJackpot();                                                                                                                                                  
    } catch (err) {                                                                                                                                                                    
      setError(err.message);                                                                                                                                                           
    } finally {                                                                                                                                                                        
      setIsSubmitting(false);                                                                                                                                                          
    }                                                                                                                                                                                  
  };                                                                                                                                                                                   
                                                                                                                                                                                       
  // Screen routing
  if (screen === 'selector') {
    return <GameSelector onGameJoined={handleGameJoined} />;
  }

  if (screen === 'lobby') {
    return (
      <GameLobby
        gameId={gameId}
        gameCode={gameCode}
        sessionToken={sessionToken}
        userId={userId}
        isHost={isHost}
        onGameStarted={handleGameStarted}
      />
    );
  }

  // Game screen - existing game board UI
  if (loading) return <div>Loading…</div>;
  if (error) return <div style={{ color: "red" }}>Error: {error}</div>;
  if (!game) return <div>No game data.</div>;

  return (                                                                                                                                                                             
    <div style={{ padding: "0.5rem 1rem", fontFamily: "sans-serif" }}>                                                                                                                 
      <div                                                                                                                                                                             
        style={{                                                                                                                                                                       
          display: "flex",                                                                                                                                                             
          gap: "5rem",                                                                                                                                                                 
          justifyContent: "center",                                                                                                                                                    
          alignItems: "flex-start",                                                                                                                                                    
          maxWidth: 1800,                                                                                                                                                              
          margin: "0 auto",                                                                                                                                                            
        }}                                                                                                                                                                             
      >
        {/* Left column: board + cards */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {/* Game heading - centered above board */}
        <h1 style={{ margin: "0 0 -4.5rem 0", fontSize: "1.5rem", textAlign: "center" }}>Game {gameId}</h1>

        {/* Board + floating controls */}
        <div style={{ position: "relative", width: 1100, height: 1100 }}>
          <Board players={game.players} currentPlayerId={game.current_player_id} />

          {/* Jackpot positioned at square 20 (Salvo Rest Home - top-left corner) */}
          {jackpot !== null && (
            <div style={{
              position: "absolute",
              top: 40,
              left: 40,
              background: "rgba(255,255,255,0.95)",
              padding: "10px 16px",
              borderRadius: 8,
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
              zIndex: 5,
              fontWeight: "bold",
              fontSize: "1.2em",
              color: "#b28500"
            }}>
              💰 Jackpot: ${jackpot}
            </div>
          )}

          {/* Trading Board Overlay */}
          {showTradingBoard && (
            <div
              onMouseDown={handleTradingBoardMouseDown}
              style={{
                position: "absolute",
                top: `${tradingBoardPos.y}px`,
                left: `${tradingBoardPos.x}px`,
                width: "900px",
                height: "850px",
                background: "#fff",
                border: "3px solid #6a4c93",
                borderRadius: "12px",
                boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
                zIndex: 100,
                display: "flex",
                flexDirection: "column"
              }}>
              <div
                className="trading-board-header"
                style={{
                  padding: "1rem 1.5rem",
                  background: "linear-gradient(135deg, #6a4c93 0%, #8b6fb0 100%)",
                  borderRadius: "9px 9px 0 0",
                  cursor: "move",
                  userSelect: "none"
                }}
              >
                <h2 style={{ margin: 0, color: "#fff", textAlign: "center", fontSize: "1.3rem" }}>Trading Board</h2>
              </div>
              <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", flex: 1 }}>

              {/* Main content area - will be filled later */}
              <div style={{
                flex: 1,
                border: "1px solid #ddd",
                borderRadius: "8px",
                padding: "1rem",
                marginBottom: "1rem",
                background: "#f9f9f9"
              }}>
                <p style={{ color: "#666", textAlign: "center", marginTop: "2rem" }}>
                  Trading interface coming soon...
                </p>
              </div>

              {/* Bottom buttons */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "1rem" }}>
                <button
                  onClick={() => setShowTradingBoard(false)}
                  style={{
                    padding: "0.6rem 1.5rem",
                    background: "#dc3545",
                    color: "#fff",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontSize: "1rem",
                    fontWeight: "bold"
                  }}
                >
                  Exit
                </button>
                <button
                  style={{
                    padding: "0.6rem 1.5rem",
                    background: "#ccc",
                    color: "#888",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "not-allowed",
                    fontSize: "1rem",
                    fontWeight: "bold"
                  }}
                  disabled
                >
                  Save (Not Working Yet)
                </button>
              </div>
              </div>
            </div>
          )}
        </div>

        {/* Card display section - below board */}
        <div style={{
          width: 1100,
          display: 'flex',
          gap: '1.5rem',
          marginTop: '1.5rem',
          justifyContent: 'center',
          position: 'relative',
          left: '100px',
          top: '-233px',
          zIndex: 10
        }}>
          {/* Welfare Centre Card */}
          <div style={{
            background: 'linear-gradient(135deg, #fff 0%, #f8f9fa 100%)',
            border: '2px solid #dee2e6',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            padding: '14px',
            minHeight: '133px',
            width: '333px',
          }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#6a4c93' }}>
              Welfare Centre
            </h3>
            {lastDrawnCards.WELFARE ? (
              <>
                <h4 style={{
                    fontSize: '0.85rem',
                    fontWeight: 'bold',
                    color: '#1982c4',
                    marginTop: '0.5rem',
                    marginBottom: '0.3rem',
                }}>
                    {lastDrawnCards.WELFARE.title}
                </h4>
                <p style={{
                    fontSize: '0.75rem',
                    lineHeight: '1.4',
                    color: '#333',
                    margin: 0,
                }}>
                    {lastDrawnCards.WELFARE.body_text}
                </p>
              </>
            ) : (
              <p style={{ fontStyle: 'italic', color: '#999', marginTop: '0.7rem', fontSize: '0.75rem' }}>
                No cards drawn yet
              </p>
            )}
          </div>

          {/* Chance Card */}
          <div style={{
            background: 'linear-gradient(135deg, #fff 0%, #f8f9fa 100%)',
            border: '2px solid #dee2e6',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            padding: '14px',
            minHeight: '133px',
            width: '333px',
          }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#ff924c' }}>
              Chance
            </h3>
            {lastDrawnCards.CHANCE ? (
              <>
                <h4 style={{
                    fontSize: '0.85rem',
                    fontWeight: 'bold',
                    color: '#1982c4',
                    marginTop: '0.5rem',
                    marginBottom: '0.3rem',
                }}>
                    {lastDrawnCards.CHANCE.title}
                </h4>
                <p style={{
                    fontSize: '0.75rem',
                    lineHeight: '1.4',
                    color: '#333',
                    margin: 0,
                }}>
                    {lastDrawnCards.CHANCE.body_text}
                </p>
              </>
            ) : (
              <p style={{ fontStyle: 'italic', color: '#999', marginTop: '0.7rem', fontSize: '0.75rem' }}>
                No cards drawn yet
              </p>
            )}
          </div>
        </div>
        </div>

        {/* Right column: player list */}
        <div
          style={{
            flex: 1,
            minWidth: 360,
            paddingLeft: "120px",
            position: "sticky",
            top: 20,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ margin: 0 }}>Players</h2>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                onClick={() => setShowTradingBoard(true)}
                style={{
                  padding: "0.5rem 1rem",
                  background: "#6a4c93",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "1rem",
                }}
              >
                Trade
              </button>
              <button
                onClick={nextTurn}
                disabled={isSubmitting || pendingAction}
                style={{
                  padding: "0.5rem 1rem",
                  background: isSubmitting || pendingAction ? "#ccc" : "#1982c4",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: isSubmitting || pendingAction ? "not-allowed" : "pointer",
                  fontSize: "1rem",
                }}
              >
                {isSubmitting ? "Processing..." : pendingAction ? "Resolve Action First" : "Next Turn"}
              </button>
            </div>
          </div>

          {lastDiceRoll && (
            <div style={{ marginBottom: "1rem", fontSize: "0.95rem", color: "#333", background: "#fff", padding: "12px 16px", borderRadius: 8, border: "2px solid #1982c4", boxShadow: "0 2px 8px rgba(0,0,0,0.15)" }}>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <span style={{ fontWeight: "bold" }}>Last Roll:</span>
                <span style={{
                  background: "#fff",
                  border: "2px solid #1982c4",
                  borderRadius: "6px",
                  padding: "0.4rem 0.6rem",
                  fontWeight: "bold",
                  fontSize: "1.1rem"
                }}>
                  {lastDiceRoll.dice_roll_1}
                </span>
                <span>+</span>
                <span style={{
                  background: "#fff",
                  border: "2px solid #1982c4",
                  borderRadius: "6px",
                  padding: "0.4rem 0.6rem",
                  fontWeight: "bold",
                  fontSize: "1.1rem"
                }}>
                  {lastDiceRoll.dice_roll_2}
                </span>
                <span>=</span>
                <span style={{ fontWeight: "bold", fontSize: "1.1rem", color: "#1982c4" }}>
                  {lastDiceRoll.total_roll}
                </span>
                {lastDiceRoll.is_double && (
                  <span style={{
                    marginLeft: "0.5rem",
                    color: "#ff6b6b",
                    fontWeight: "bold",
                    fontSize: "0.9rem"
                  }}>
                    DOUBLE!
                  </span>
                )}
              </div>
            </div>
          )}

          <ul style={{ paddingLeft: "1rem" }}>
            {game.players?.map((p) => {
              // Convert from 1-based space_id to 0-based array index
              const idx = (p.current_space_id ?? 1) - 1;
              const spaceLabel = SPACE_LABELS[idx];
              const cash = playerBalances[String(p.game_player_id)] ?? "?";
              const assets = allPlayerAssets[p.game_player_id] || allPlayerAssets[String(p.game_player_id)] || [];
              const retained = playerRetainedCards[p.game_player_id] || [];
              const isCurrent = p.game_player_id === game.current_player_id;

              // Calculate next player based on turn_order
              // Don't show "next" if current player rolled a double (they get another turn)
              const currentPlayer = game.players.find(pl => pl.game_player_id === game.current_player_id);
              const nextTurnOrder = currentPlayer ? ((currentPlayer.turn_order % game.players.length) + 1) : 1;
              const rolledDouble = lastDiceRoll?.is_double && !currentPlayer?.in_jail;
              const isNext = p.turn_order === nextTurnOrder && !isCurrent && !rolledDouble;
              return (
                <li key={p.game_player_id} style={{
                  marginBottom: 12,
                  padding: "12px",
                  borderRadius: "8px",
                  background: isCurrent ? "linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)" : "transparent",
                  border: isCurrent ? "3px solid #1982c4" : isNext ? "2px dashed #ff924c" : "1px solid #e0e0e0",
                  position: "relative",
                  boxShadow: isCurrent ? "0 2px 8px rgba(25, 130, 196, 0.3)" : "none"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.8rem", marginBottom: "6px" }}>
                    <strong style={{ fontSize: "1.1rem" }}>{p.player_name}</strong>
                    <span>
                      {spaceLabel}
                      {" – "}
                      <span style={{ color: "#1982c4" }}>
                        Cash: <b>${cash}</b>
                      </span>
                      {p.in_jail ? " (In Jail)" : ""}
                    </span>
                    {isCurrent && (
                      <span style={{
                        background: "#1982c4",
                        color: "#fff",
                        padding: "6px 14px",
                        borderRadius: "6px",
                        fontSize: "0.9rem",
                        fontWeight: "bold",
                        letterSpacing: "0.5px",
                        boxShadow: "0 2px 4px rgba(0,0,0,0.2)"
                      }}>
                        ▶ CURRENT PLAYER
                      </span>
                    )}
                    {isCurrent && rolledDouble && (
                      <span style={{
                        background: "#ff6b6b",
                        color: "#fff",
                        padding: "6px 14px",
                        borderRadius: "6px",
                        fontSize: "0.9rem",
                        fontWeight: "bold",
                        letterSpacing: "0.5px",
                        boxShadow: "0 2px 4px rgba(0,0,0,0.2)"
                      }}>
                        ROLL AGAIN!
                      </span>
                    )}
                    {isNext && !isCurrent && (
                      <span style={{
                        background: "#ff924c",
                        color: "#fff",
                        padding: "6px 14px",
                        borderRadius: "6px",
                        fontSize: "0.9rem",
                        fontWeight: "bold",
                        letterSpacing: "0.5px",
                        boxShadow: "0 2px 4px rgba(0,0,0,0.2)"
                      }}>
                        NEXT →
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: "0.95em", color: "#222" }}>
                    {assets.length > 0 ? (
                      <>
                        <span>Props: </span>
                        {assets.map((a, i) => (
                          <span key={a.asset_id} style={{ marginRight: 4 }}>
                            {a.name}
                            {a.improvement_level > 0 ? ` (${a.improvement_level} house${a.improvement_level > 1 ? "s" : ""})` : ""}
                            {a.has_hotel ? " (hotel)" : ""}
                            {a.is_mortgaged ? " (mortgaged)" : ""}
                            {i < assets.length - 1 ? ", " : ""}
                          </span>
                        ))}
                      </>
                    ) : (
                      <span>Props: —</span>
                    )}
                  </div>
                  {retained.length > 0 && (
                    <div style={{ fontSize: "0.9em", color: "#6a4c93", marginTop: "4px" }}>
                      🃏 Cards: {retained.map((card, i) => (
                        <span key={i} style={{ marginRight: 4 }}>
                          {card.name || card.title || card.description}
                          {i < retained.length - 1 ? ", " : ""}
                        </span>
                      ))}
                    </div>
                  )}                                                                                                                                                                   
                </li>                                                                                                                                                                  
              );                                                                                                                                                                       
            })}                                                                                                                                                                        
          </ul>

          {/* Ledger section below Players */}
          <div style={{
            marginTop: "2rem",
            background: "rgba(255,255,255,0.95)",
            padding: "12px 16px",
            borderRadius: 8,
            boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
            maxHeight: 400,
            overflowY: "auto"
          }}>
            <h3 style={{ margin: "0 0 8px 0", fontSize: "1.1rem" }}>Ledger (latest)</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #ccc" }}>
                  <th align="left">Type</th>
                  <th align="left">Amount</th>
                  <th align="left">From</th>
                  <th align="left">To</th>
                </tr>
              </thead>
              <tbody>
                {ledger.slice(0, 7).map((txn) => (
                  <tr key={txn.id} style={{ borderBottom: "1px solid #eee" }}>
                    <td>{txn.type}</td>
                    <td>${txn.amount}</td>
                    <td>{txn.from ?? "BANK"}</td>
                    <td>{txn.to ?? "BANK"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

        </div>
      </div>

      {/* Purchase/Auction Modals */}
      {pendingAction && pendingAction.action_type === "purchase_decision" && (
        <PurchaseModal
          gameId={gameId}
          sessionToken={sessionToken}
          pendingAction={pendingAction}
          playerBalances={playerBalances}
          players={game.players}
          onResolved={fetchGameLedgerJackpot}
        />
      )}

      {pendingAction && pendingAction.action_type === "auction" && (
        <AuctionModal
          gameId={gameId}
          sessionToken={sessionToken}
          pendingAction={pendingAction}
          playerBalances={playerBalances}
          players={game.players}
          onResolved={fetchGameLedgerJackpot}
        />
      )}
    </div>
  );
}

export default App;       