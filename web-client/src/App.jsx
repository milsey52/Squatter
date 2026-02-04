import { useEffect, useState, useCallback, useMemo } from "react";
import Board from "./Board";
import PurchaseModal from "./PurchaseModal";
import AuctionModal from "./AuctionModal";
import CardModal from "./components/CardModal";
import RentPaymentModal from "./components/RentPaymentModal";
import JailModal from "./components/JailModal";
import RetainedCardPopup from "./components/RetainedCardPopup";
import GameSelector from "./components/GameSelector";
import GameLobby from "./components/GameLobby";
import SuspendedGameNotice from "./components/SuspendedGameNotice";
import JailTurnOptions from "./components/JailTurnOptions";
import TradingBoard from "./components/TradingBoard";
import PropertyManagement from "./components/PropertyManagement";
import PropertyLedger from "./components/PropertyLedger";
import WorthModal from "./components/WorthModal";
import BankruptcyModal from "./components/BankruptcyModal";
import { useGameEvents } from "./hooks/useGameEvents";

const API_BASE = import.meta.env.VITE_API_BASE || '';                                                                                                             
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
  const [diceRolls, setDiceRolls] = useState([]);
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
  const [selectedCard, setSelectedCard] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [activeTrade, setActiveTrade] = useState(null);
  const [showPropertyManagement, setShowPropertyManagement] = useState(false);
  const [showWorthModal, setShowWorthModal] = useState(false);
  const [bankruptcyInfo, setBankruptcyInfo] = useState(null);
  const [showBankruptcyModal, setShowBankruptcyModal] = useState(false);
  const [gameOver, setGameOver] = useState(false);
  const [jailChoiceMade, setJailChoiceMade] = useState(false);
  const [winner, setWinner] = useState(null);
  const [animatedPositions, setAnimatedPositions] = useState({});
  const [isAnimating, setIsAnimating] = useState(false);

  // Create a map of board_index -> {improvement_level, has_hotel} for board display
  const propertyImprovements = useMemo(() => {
    const improvements = {};

    // Flatten allPlayerAssets into a map keyed by board_index (0-39)
    Object.values(allPlayerAssets).forEach(playerAssets => {
      if (Array.isArray(playerAssets)) {
        playerAssets.forEach(asset => {
          if (asset.asset_type === 'property' && asset.board_index !== undefined && asset.board_index !== null) {
            improvements[asset.board_index] = {
              improvement_level: asset.improvement_level || 0,
              has_hotel: asset.has_hotel || false
            };
          }
        });
      }
    });

    return improvements;
  }, [allPlayerAssets]);

  // Handle game joined from selector
  const handleGameJoined = (data) => {
    console.log('[App] handleGameJoined called with data:', data);
    setGameId(data.gameId);
    setGameCode(data.gameCode);
    setSessionToken(data.sessionToken);
    setUserId(data.userId);
    setIsHost(data.isHost);

    // Save session token to localStorage
    localStorage.setItem('monopoly_session_token', data.sessionToken);
    console.log('[App] Session token saved. Navigating to lobby...');

    // Navigate based on game status
    if (data.gameStatus === 'in_progress' || data.gameStatus === 'suspended') {
      setScreen('game');
    } else {
      // lobby or rolling_for_order - stay in lobby
      setScreen('lobby');
    }
  };

  // Handle game started from lobby
  const handleGameStarted = () => {
    setScreen('game');
  };

  const handleLogout = async () => {
    if (!gameId || !sessionToken) return;

    const confirmLogout = window.confirm(
      'Are you sure you want to logout? This will suspend the game for all players until you log back in.'
    );

    if (!confirmLogout) return;

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/logout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (response.ok) {
        // Don't clear session token - keep it so player can log back in
        // Just navigate to selector screen
        setScreen('selector');
        alert('You have been logged out. Visit the game link or enter the game code to log back in.');
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to logout');
      }
    } catch (error) {
      console.error('Error logging out:', error);
      alert('Failed to logout');
    }
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
        .then(async data => {
          // Restore session state
          setSessionToken(token);
          setGameId(data.game_id);
          setGameCode(data.game_code);
          setUserId(data.user_id);
          setIsHost(data.is_host);

          // If game is suspended, automatically log player back in
          if (data.game_status === 'suspended') {
            try {
              await fetch(`${API_BASE}/games/${data.game_id}/login`, {
                method: 'POST',
                headers: {
                  'Authorization': `Bearer ${token}`
                }
              });
              console.log('[App] Auto-logged in after returning to suspended game');
            } catch (err) {
              console.error('[App] Auto-login failed:', err);
            }
          }

          // Navigate to appropriate screen
          if (data.game_status === 'lobby' || data.game_status === 'rolling_for_order') {
            // Keep players in lobby during turn order rolling
            setScreen('lobby');
          } else if (data.game_status === 'in_progress' || data.game_status === 'suspended') {
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

    const [gameRes, ledgerRes, jackpotRes, balancesRes, assetsRes, cardsRes, lastDrawnCardsRes, pendingRes, tradeRes, diceRollsRes] = await Promise.all([
      fetch(`${API_BASE}/games/${gameId}`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/ledger`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/jackpot`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/player_balances`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/player_assets`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/player_retained_cards`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/last_drawn_cards`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/pending-action`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/trades/active`, { headers }),
      fetch(`${API_BASE}/games/${gameId}/dice_rolls`, { headers })
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
    const tradeData = tradeRes.ok ? await tradeRes.json() : { trade: null };
    const diceRollsData = diceRollsRes.ok ? await diceRollsRes.json() : { rolls: [] };

    setGame(gameData);
    setLedger(Array.isArray(ledgerData) ? ledgerData : []);
    setDiceRolls(diceRollsData.rolls || []);
    setJackpot(jackpotData.jackpot);
    setPlayerBalances(balancesData);
    setAllPlayerAssets(assetsData);
    setPlayerRetainedCards(cardsData);
    setLastDrawnCards(lastDrawnCardsData);
    setPendingAction(pendingData.pending_action);
    setActiveTrade(tradeData.trade);
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
        setActiveTrade(null);
      })
      .finally(() => setLoading(false));

    // Poll for trade updates every 3 seconds as backup to SSE
    const pollInterval = setInterval(() => {
      fetch(`${API_BASE}/games/${gameId}/trades/active`, {
        headers: sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {}
      })
        .then(res => {
          if (!res.ok) {
            // Silently ignore 404 or other errors - no active trade
            return { trade: null };
          }
          return res.json();
        })
        .then(data => {
          setActiveTrade(prevTrade => {
            // If no active trade, clear the state
            if (!data.trade) {
              if (prevTrade !== null) {
                console.log('[Poll] Trade cleared');
              }
              return null;
            }
            // If trade exists and is different, update it
            if (JSON.stringify(data.trade) !== JSON.stringify(prevTrade)) {
              console.log('[Poll] Trade updated:', data.trade);
              return data.trade;
            }
            return prevTrade;
          });
        })
        .catch(err => console.error('[Poll] Error fetching trade:', err));
    }, 3000);

    return () => clearInterval(pollInterval);
  }, [screen, gameId, sessionToken, fetchGameLedgerJackpot]);

  // Animate token movement step-by-step
  const animateTokenMovement = useCallback(async (playerId, startPosition, diceTotal) => {
    const BOARD_SIZE = 40;
    const STEP_DELAY = 300; // milliseconds between each space

    setIsAnimating(true);

    // Animate through each space
    for (let step = 1; step <= diceTotal; step++) {
      await new Promise(resolve => setTimeout(resolve, STEP_DELAY));
      const newPosition = (startPosition + step) % BOARD_SIZE;

      setAnimatedPositions(prev => ({
        ...prev,
        [playerId]: newPosition
      }));
    }

    setIsAnimating(false);

    // Don't clear animated position here - let it persist until database updates
    // This prevents the token from jumping back to the old position
  }, []);

  // Handle real-time game events
  const handleGameEvent = useCallback((eventType, data) => {
    console.log('[App] Game event received:', eventType, data);

    switch (eventType) {
      case 'turn_played':
        // Reset jail choice when a turn is played
        setJailChoiceMade(false);
        // Update dice roll display for all players
        if (data.dice_roll && data.dice_roll.length === 2) {
          setLastDiceRoll({
            dice_roll_1: data.dice_roll[0],
            dice_roll_2: data.dice_roll[1],
            total_roll: data.dice_roll[0] + data.dice_roll[1],
            is_double: data.is_double,
            player_id: data.player_id  // Track who rolled
          });

          const diceTotal = data.dice_roll[0] + data.dice_roll[1];
          const movingPlayerId = data.player_id;
          const movingPlayer = game?.players?.find(p => p.game_player_id === movingPlayerId);

          if (movingPlayer && diceTotal > 0) {
            const startPosition = movingPlayer.current_space_id;

            // Animate token movement, then show modals after delay
            animateTokenMovement(movingPlayerId, startPosition, diceTotal).then(() => {
              // Delay before showing any modals (rent, cards, etc.)
              setTimeout(() => {
                fetchGameLedgerJackpot().then(() => {
                  // Clear animated position after database is updated
                  setAnimatedPositions(prev => {
                    const newPositions = { ...prev };
                    delete newPositions[movingPlayerId];
                    return newPositions;
                  });
                });
              }, 500);
            });
          } else {
            // No animation needed, just refresh
            fetchGameLedgerJackpot();
          }
        } else {
          // No dice roll data, just refresh
          fetchGameLedgerJackpot();
        }
        break;
      case 'bankruptcy_triggered':
        console.log('[App] Bankruptcy triggered:', data);
        // Refresh to show updated state
        fetchGameLedgerJackpot();
        break;
      case 'debt_resolved':
        console.log('[App] Debt resolved:', data);
        fetchGameLedgerJackpot();
        break;
      case 'player_resigned':
        console.log('[App] Player resigned:', data);
        alert(`${data.player_name} has resigned from the game.`);
        fetchGameLedgerJackpot();
        break;
      case 'game_over':
        console.log('[App] Game over:', data);
        setGameOver(true);
        setWinner(data.winner_name);
        fetchGameLedgerJackpot();
        break;
      case 'game_state_changed':
      case 'auction_started':
      case 'auction_bid':
      case 'auction_pass':
      case 'auction_resolved':
      case 'trade_initiated':
      case 'trade_status_changed':
      case 'trade_offer_updated':
      case 'trade_cancelled':
      case 'trade_executed':
        // Refresh game state when any of these events occur
        fetchGameLedgerJackpot();
        break;
      default:
        break;
    }
  }, [fetchGameLedgerJackpot, game, animateTokenMovement]);

  // Connect to SSE for real-time updates when in game screen
  useGameEvents(
    screen === 'game' ? gameId : null,
    screen === 'game' ? sessionToken : null,
    handleGameEvent
  );

  // Auto-show trading board when user receives a trade invitation
  useEffect(() => {
    if (screen !== 'game' || !game || !activeTrade) return;

    const currentUserPlayer = game.players?.find(p => p.user_id === userId);
    if (!currentUserPlayer) return;

    // Check if this user is the counterparty and the trade is pending invite
    const isCounterparty = activeTrade.counterparty_player_id === currentUserPlayer.game_player_id;
    const isPendingInvite = activeTrade.status === 'pending_invite';

    console.log('[Auto-show trade] isCounterparty:', isCounterparty, 'isPendingInvite:', isPendingInvite, 'showTradingBoard:', showTradingBoard);
    console.log('[Auto-show trade] activeTrade:', activeTrade);
    console.log('[Auto-show trade] currentUserPlayer:', currentUserPlayer);

    if (isCounterparty && isPendingInvite && !showTradingBoard) {
      console.log('[Auto-show trade] OPENING TRADING BOARD');
      setShowTradingBoard(true);
    }
  }, [activeTrade, game, userId, screen, showTradingBoard]);

  // Handle bankruptcy
  const handleBankruptcy = useCallback((debtData) => {
    console.log('[App] Bankruptcy triggered with debt data:', debtData);
    setBankruptcyInfo(debtData);
    setShowBankruptcyModal(true);
  }, []);

  const handleBankruptcyLiquidate = useCallback(() => {
    setShowBankruptcyModal(false);
    setShowPropertyManagement(true);
  }, []);

  const handleBankruptcyTrade = useCallback(() => {
    setShowBankruptcyModal(false);
    setShowTradingBoard(true);
  }, []);

  const handleBankruptcyResign = useCallback(() => {
    fetchGameLedgerJackpot();
  }, [fetchGameLedgerJackpot]);

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
      // Don't fetch game state here - let SSE handler do it with animation
      // The turn_played event will trigger animation and delayed state update
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
    // Ensure we have session data before rendering lobby
    if (!gameId || !sessionToken || !userId) {
      return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading lobby...</div>;
    }

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

  // Find the current user's game_player_id
  const currentUserPlayer = game.players?.find(p => p.user_id === userId);
  const isCurrentPlayer = currentUserPlayer && currentUserPlayer.game_player_id === game.current_player_id;

  // Check if current user is part of active trade
  const isPartOfActiveTrade = activeTrade && currentUserPlayer && (
    activeTrade.initiator_player_id === currentUserPlayer.game_player_id ||
    activeTrade.counterparty_player_id === currentUserPlayer.game_player_id
  );

  // Check if current user has a pending invitation
  const hasPendingInvitation = activeTrade && currentUserPlayer &&
    activeTrade.counterparty_player_id === currentUserPlayer.game_player_id &&
    activeTrade.status === 'pending_invite';

  // Disable Trade button if there's an active trade and user is not part of it
  const canStartTrade = !activeTrade || isPartOfActiveTrade;

  return (
    <div style={{ padding: "0.5rem 1rem", fontFamily: "sans-serif", position: "relative" }}>
      {/* Logout Button */}
      <button
        onClick={handleLogout}
        style={{
          position: "fixed",
          top: "1rem",
          right: "1rem",
          padding: "0.75rem 1.5rem",
          background: "#dc3545",
          color: "white",
          border: "none",
          borderRadius: "8px",
          fontSize: "1rem",
          fontWeight: "bold",
          cursor: "pointer",
          zIndex: 1001,
          boxShadow: "0 4px 8px rgba(0,0,0,0.2)"
        }}
        onMouseEnter={(e) => e.target.style.background = "#c82333"}
        onMouseLeave={(e) => e.target.style.background = "#dc3545"}
      >
        🚪 Logout
      </button>

      {/* Suspended Game Notice */}
      {game && game.status === 'suspended' && (
        <SuspendedGameNotice
          gameId={gameId}
          sessionToken={sessionToken}
        />
      )}

      {/* Trade Invitation Banner */}
      {hasPendingInvitation && !showTradingBoard && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          background: "linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%)",
          color: "#fff",
          padding: "1rem",
          textAlign: "center",
          zIndex: 1000,
          boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
          fontSize: "1.1rem",
          fontWeight: "bold"
        }}>
          🔔 {game.players?.find(p => p.game_player_id === activeTrade.initiator_player_id)?.player_name} has invited you to trade!
          <button
            onClick={() => setShowTradingBoard(true)}
            style={{
              marginLeft: "1rem",
              padding: "0.5rem 1.5rem",
              background: "#fff",
              color: "#ff6b6b",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
              fontWeight: "bold",
              fontSize: "1rem"
            }}
          >
            View Invitation
          </button>
        </div>
      )}
      <div
        style={{
          display: "flex",
          gap: "2rem",
          justifyContent: "center",
          alignItems: "flex-start",
          maxWidth: 2200,
          margin: "0 auto",
          marginTop: hasPendingInvitation && !showTradingBoard ? "4rem" : "0"
        }}                                                                                                                                                                             
      >
        {/* Left column: board + cards */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          flexShrink: 0,
          width: 1100
        }}>
        {/* Game heading - centered above board */}
        <h1 style={{ margin: "0 0 -4.5rem 0", fontSize: "1.5rem", textAlign: "center" }}>
          Game {gameId} - {currentUserPlayer?.player_name || 'Unknown Player'}
        </h1>

        {/* Board + floating controls */}
        <div style={{ position: "relative", width: 1100, height: 1100 }}>
          <Board
            players={game.players || []}
            currentPlayerId={game.current_player_id}
            propertyImprovements={propertyImprovements}
            animatedPositions={animatedPositions}
          />

          {/* Jackpot positioned at square 20 (Salvo Rest Home - top-left corner) */}
          {jackpot !== null && (
            <div style={{
              position: "absolute",
              top: 140,
              left: 44,
              background: "rgba(255,255,255,0.95)",
              padding: "10px 16px",
              borderRadius: 8,
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
              zIndex: 5,
              fontWeight: "bold",
              fontSize: "1.2em",
              color: "#b28500"
            }}>
              Jackpot: {jackpot}
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
              <TradingBoard
                gameId={gameId}
                sessionToken={sessionToken}
                userId={userId}
                game={game}
                playerBalances={playerBalances}
                allPlayerAssets={allPlayerAssets}
                playerRetainedCards={playerRetainedCards}
                activeTradeFromParent={activeTrade}
                onClose={() => setShowTradingBoard(false)}
              />
            </div>
          )}

          {/* Property Management Overlay */}
          {showPropertyManagement && (
            <div style={{
              position: "absolute",
              top: "150px",
              left: "100px",
              width: "800px",
              height: "700px",
              background: "#fff",
              border: "3px solid #4caf50",
              borderRadius: "12px",
              boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
              zIndex: 100,
              display: "flex",
              flexDirection: "column"
            }}>
              <PropertyManagement
                gameId={gameId}
                sessionToken={sessionToken}
                playerBalance={currentUserPlayer ? (playerBalances[String(currentUserPlayer.game_player_id)] ?? 0) : 0}
                onClose={() => setShowPropertyManagement(false)}
                onUpdate={fetchGameLedgerJackpot}
                liquidationMode={showBankruptcyModal || bankruptcyInfo !== null}
              />
            </div>
          )}

          {/* Worth Modal */}
          {showWorthModal && (
            <WorthModal
              gameId={gameId}
              sessionToken={sessionToken}
              onClose={() => setShowWorthModal(false)}
            />
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
            minWidth: 450,
            maxWidth: 550,
            marginLeft: "10rem",
            position: "sticky",
            top: 20,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ margin: 0 }}>Players</h2>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                onClick={() => setShowPropertyManagement(true)}
                style={{
                  padding: "0.5rem 1rem",
                  background: "#4caf50",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "1rem",
                }}
                title="Manage your properties - buy/sell houses and hotels"
              >
                🏠 Properties
              </button>
              <button
                onClick={() => setShowWorthModal(true)}
                style={{
                  padding: "0.5rem 1rem",
                  background: "#667eea",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "1rem",
                }}
                title="View your total net worth"
              >
                💰 Worth
              </button>
              <button
                onClick={() => setShowTradingBoard(true)}
                disabled={!canStartTrade}
                style={{
                  padding: "0.5rem 1rem",
                  background: !canStartTrade ? "#ccc" : hasPendingInvitation ? "#ff6b6b" : "#6a4c93",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: !canStartTrade ? "not-allowed" : "pointer",
                  fontSize: "1rem",
                  position: "relative",
                  animation: hasPendingInvitation ? "pulse 2s infinite" : "none"
                }}
                title={!canStartTrade ? "Another trade is in progress" : hasPendingInvitation ? "You have a trade invitation!" : ""}
              >
                {hasPendingInvitation ? "Trade Invite! 🔔" : "Trade"}
              </button>
              <button
                onClick={nextTurn}
                disabled={isSubmitting || pendingAction || !isCurrentPlayer ||
                         (currentUserPlayer?.in_jail && !jailChoiceMade && (!lastDiceRoll || lastDiceRoll.player_id !== currentUserPlayer.game_player_id))}
                style={{
                  padding: "0.5rem 1rem",
                  background: isSubmitting || pendingAction || !isCurrentPlayer ||
                             (currentUserPlayer?.in_jail && !jailChoiceMade && (!lastDiceRoll || lastDiceRoll.player_id !== currentUserPlayer.game_player_id)) ? "#ccc" : "#1982c4",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: isSubmitting || pendingAction || !isCurrentPlayer ||
                         (currentUserPlayer?.in_jail && !jailChoiceMade && (!lastDiceRoll || lastDiceRoll.player_id !== currentUserPlayer.game_player_id)) ? "not-allowed" : "pointer",
                  fontSize: "1rem",
                }}
              >
                {isSubmitting
                  ? "Processing..."
                  : pendingAction
                  ? "Resolve Action First"
                  : (currentUserPlayer?.in_jail && !jailChoiceMade && (!lastDiceRoll || lastDiceRoll.player_id !== currentUserPlayer.game_player_id))
                  ? "Choose Jail Action First"
                  : !isCurrentPlayer
                  ? `${game.players?.find(p => p.game_player_id === game.current_player_id)?.player_name || 'Player'}'s Turn`
                  : `${currentUserPlayer?.player_name || 'Your'} Turn - Roll Dice`}
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
              // With 0-based indexing, current_space_id is already the array index
              const idx = p.current_space_id ?? 0;
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
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.8rem" }}>
                      <strong style={{ fontSize: "1.1rem", color: "#333" }}>{p.player_name}</strong>
                      <span style={{ fontSize: "0.9rem", color: "#555" }}>
                        📍 {p.in_jail ? "In Jail" : spaceLabel}
                      </span>
                      <span style={{ fontSize: "0.9rem", color: "#1982c4" }}>
                        💰 <b>${cash}</b>
                      </span>
                    </div>
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
                  </div>
                  {retained.length > 0 && (
                    <div style={{ fontSize: "0.9em", color: "#6a4c93", marginTop: "4px" }}>
                      🃏 {retained.map((card, i) => (
                        <span key={i}>
                          <button
                            onClick={() => setSelectedCard(card)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#6a4c93',
                              textDecoration: 'underline',
                              cursor: 'pointer',
                              padding: 0,
                              font: 'inherit',
                              marginRight: 4
                            }}
                            title="Click to view full card details"
                          >
                            {card.title || card.name || 'Card'}
                          </button>
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
            <h3 style={{ margin: "0 0 8px 0", fontSize: "1.1rem", color: "#333" }}>Ledger (latest)</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #ccc" }}>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>Type</th>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>Amount</th>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>Asset</th>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>From</th>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>To</th>
                </tr>
              </thead>
              <tbody>
                {ledger.slice(0, 7).map((txn) => (
                  <tr key={txn.id} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={{ color: "#555", padding: "6px 4px" }}>{txn.type}</td>
                    <td style={{ color: "#555", padding: "6px 4px" }}>${txn.amount}</td>
                    <td style={{ fontSize: "0.8rem", color: "#666", padding: "6px 4px" }}>{txn.asset_name || "-"}</td>
                    <td style={{ color: "#555", padding: "6px 4px" }}>{txn.from ?? "BANK"}</td>
                    <td style={{ color: "#555", padding: "6px 4px" }}>{txn.to ?? "BANK"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Dice Rolls Register */}
          <div style={{
            marginTop: "2rem",
            background: "rgba(255,255,255,0.95)",
            padding: "12px 16px",
            borderRadius: 8,
            boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
            maxHeight: 400,
            overflowY: "auto"
          }}>
            <h3 style={{ margin: "0 0 8px 0", fontSize: "1.1rem", color: "#333" }}>Dice Roll Register</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #ccc" }}>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>Roll #</th>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>Who</th>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>Dice</th>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>From</th>
                  <th align="left" style={{ color: "#333", padding: "6px 4px" }}>To</th>
                </tr>
              </thead>
              <tbody>
                {diceRolls.map((roll) => (
                  <tr key={roll.roll_number} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={{ color: "#555", padding: "6px 4px" }}>{roll.roll_number}</td>
                    <td style={{ color: "#555", padding: "6px 4px" }}>{roll.player}</td>
                    <td style={{ color: "#555", padding: "6px 4px" }}>
                      {roll.dice1} + {roll.dice2} = {roll.total}
                    </td>
                    <td style={{ fontSize: "0.8rem", color: "#666", padding: "6px 4px" }}>{roll.from_location || "—"}</td>
                    <td style={{ fontSize: "0.8rem", color: "#666", padding: "6px 4px" }}>{roll.to_location || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

        </div>

        {/* Third column: Property Ledger */}
        <div style={{
          minWidth: 400,
          maxWidth: 480,
          marginLeft: "2rem",
          flexShrink: 0,
          position: "sticky",
          top: 20,
        }}>
          <PropertyLedger
            gameId={gameId}
            sessionToken={sessionToken}
          />
        </div>
      </div>

      {/* Purchase/Auction Modals */}
      {pendingAction && pendingAction.action_type === "purchase_decision" && (
        <PurchaseModal
          gameId={gameId}
          sessionToken={sessionToken}
          userId={userId}
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
          userId={userId}
          pendingAction={pendingAction}
          playerBalances={playerBalances}
          players={game.players}
          onResolved={fetchGameLedgerJackpot}
        />
      )}

      {/* Card Modal for Chance/Welfare */}
      {pendingAction && pendingAction.action_type === "card_drawn" && (
        <CardModal
          gameId={gameId}
          sessionToken={sessionToken}
          userId={userId}
          pendingAction={pendingAction}
          players={game?.players || []}
          onResolved={fetchGameLedgerJackpot}
        />
      )}

      {/* Rent Payment Modal */}
      {pendingAction && pendingAction.action_type === "rent_payment" && (
        <RentPaymentModal
          gameId={gameId}
          sessionToken={sessionToken}
          pendingAction={pendingAction}
          playerBalances={playerBalances}
          onResolved={fetchGameLedgerJackpot}
          onBankruptcy={handleBankruptcy}
          userId={userId}
          players={game?.players || []}
        />
      )}

      {/* Jail Turn Options - Show when it's jailed player's turn */}
      {isCurrentPlayer && currentUserPlayer && currentUserPlayer.in_jail &&
       (!lastDiceRoll || lastDiceRoll.player_id !== currentUserPlayer.game_player_id) &&
       !pendingAction && !jailChoiceMade && (
        <JailTurnOptions
          gameId={gameId}
          sessionToken={sessionToken}
          onAction={() => {
            setJailChoiceMade(true);
            fetchGameLedgerJackpot();
          }}
        />
      )}

      {/* Jail Notification Modal */}
      {pendingAction && pendingAction.action_type === "jail_notification" && (
        <JailModal
          gameId={gameId}
          sessionToken={sessionToken}
          userId={userId}
          pendingAction={pendingAction}
          players={game?.players || []}
          onResolved={fetchGameLedgerJackpot}
        />
      )}

      {/* Retained Card Details Popup */}
      {selectedCard && (
        <RetainedCardPopup
          card={selectedCard}
          onClose={() => setSelectedCard(null)}
        />
      )}

      {/* Bankruptcy Modal */}
      {showBankruptcyModal && bankruptcyInfo && (
        <BankruptcyModal
          gameId={gameId}
          debtInfo={bankruptcyInfo}
          onClose={() => setShowBankruptcyModal(false)}
          onLiquidate={handleBankruptcyLiquidate}
          onTrade={handleBankruptcyTrade}
          onResign={handleBankruptcyResign}
          sessionToken={sessionToken}
        />
      )}

      {/* Game Over Screen */}
      {gameOver && winner && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 10000
        }}>
          <div style={{
            background: 'linear-gradient(135deg, #ffd700 0%, #ffed4e 100%)',
            borderRadius: '20px',
            padding: '3rem',
            textAlign: 'center',
            maxWidth: '600px',
            boxShadow: '0 10px 50px rgba(255, 215, 0, 0.5)'
          }}>
            <h1 style={{
              fontSize: '3rem',
              margin: '0 0 1rem 0',
              color: '#333'
            }}>
              🏆 GAME OVER 🏆
            </h1>
            <h2 style={{
              fontSize: '2rem',
              margin: '0 0 2rem 0',
              color: '#555'
            }}>
              {winner} Wins!
            </h2>
            <p style={{
              fontSize: '1.2rem',
              color: '#666',
              marginBottom: '2rem'
            }}>
              Congratulations on monopolizing Perth!
            </p>
            <button
              onClick={() => {
                setGameOver(false);
                setWinner(null);
                setScreen('selector');
              }}
              style={{
                padding: '1rem 2rem',
                background: '#4caf50',
                color: '#fff',
                border: 'none',
                borderRadius: '10px',
                fontSize: '1.2rem',
                fontWeight: 'bold',
                cursor: 'pointer'
              }}
            >
              Return to Lobby
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;       