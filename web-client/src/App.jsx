import { useEffect, useState, useCallback, useRef } from "react";
import Board from "./Board";
import GameSelector from "./components/GameSelector";
import GameLobby from "./components/GameLobby";
import SuspendedGameNotice from "./components/SuspendedGameNotice";
import RetainedCardPopup from "./components/RetainedCardPopup";
import HoldingsPanel from "./components/HoldingsPanel";
import TradingBoard from "./components/TradingBoard";
import StationPanel from "./components/StationPanel";
import PendingActionModal from "./components/PendingActionModal";
import PlayerStationModal from "./components/PlayerStationModal";
import { useGameEvents } from "./hooks/useGameEvents";
import { Z_INDEX } from "./constants/zIndex";

const API_BASE = import.meta.env.VITE_API_BASE || '';

const SPACE_LABELS = [
  "Start/Wool Sale", "Stock Sale", "Sheep Dipping", "Stud Ram – Elmsford",
  "Tucker Bag", "Bore Dries Up", "Visiting Town", "Visiting Town",
  "Drench Sheep for Worms", "Tucker Bag", "Flood Damage", "Tucker Bag",
  "Stock Sale", "Fly Strike Dip", "Control of Vermin", "Stock Sale",
  "Footrot Treatment", "Stock Sale", "Stud Ram – Lachlan Lad", "Tucker Bag",
  "Fencing Repairs", "Spray for Weeds & Insects", "Local Drought", "Liver Fluke Drench",
  "Tucker Bag", "Stock Sale", "Stud Ram – King of Warramboo", "Local Rain",
  "Stock Sale", "Pulpy Kidney Vaccine", "Stud Ram – Winton Boy", "Tucker Bag",
  "Stock Sale", "Stud Ram Dies", "Water Drilling", "Tucker Bag",
  "Stock Sale", "Fertilising Pasture", "Stock Sale", "Stud Ram – Mitchell's Pride",
  "Shearing Costs", "Tucker Bag", "Stock Sale", "Local Drought"
];

function App() {
  // Routing and session state
  const [screen, setScreen] = useState('selector');
  const [gameId, setGameId] = useState(null);
  const [gameCode, setGameCode] = useState(null);
  const [sessionToken, setSessionToken] = useState(localStorage.getItem('squatter_session_token'));
  const [userId, setUserId] = useState(null);
  const [isHost, setIsHost] = useState(false);

  // Game state
  const [game, setGame] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [diceRolls, setDiceRolls] = useState([]);
  const [playerBalances, setPlayerBalances] = useState({});
  const [stations, setStations] = useState({});
  const [studRams, setStudRams] = useState([]);
  const [playerRetainedCards, setPlayerRetainedCards] = useState({});
  const [lastDrawnCard, setLastDrawnCard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastDiceRoll, setLastDiceRoll] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [showTradingBoard, setShowTradingBoard] = useState(false);
  const [showStationPanel, setShowStationPanel] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);
  const [viewingPlayerId, setViewingPlayerId] = useState(null);
  const [holdingsRefreshKey, setHoldingsRefreshKey] = useState(0);
  const [activeTrade, setActiveTrade] = useState(null);
  const [gameOver, setGameOver] = useState(false);
  const [winner, setWinner] = useState(null);
  const [animatedPositions, setAnimatedPositions] = useState({});
  const [animatingPlayers, setAnimatingPlayers] = useState(new Set());
  const animatingPlayersRef = useRef(new Set());
  const fetchAbortControllerRef = useRef(null);
  const lastFetchRef = useRef(0);
  const pendingFetchRef = useRef(false);
  const fetchGameStateRef = useRef(null);

  // Handle game joined from selector
  const handleGameJoined = (data) => {
    setGameId(data.gameId);
    setGameCode(data.gameCode);
    setSessionToken(data.sessionToken);
    setUserId(data.userId);
    setIsHost(data.isHost);
    localStorage.setItem('squatter_session_token', data.sessionToken);

    if (data.gameStatus === 'in_progress' || data.gameStatus === 'suspended') {
      setScreen('game');
    } else {
      setScreen('lobby');
    }
  };

  const handleGameStarted = () => setScreen('game');

  const handleLogout = async () => {
    if (!gameId || !sessionToken) return;
    if (!window.confirm('Logout will suspend the game for all players. Continue?')) return;

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/logout`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${sessionToken}` }
      });
      if (response.ok) {
        setScreen('selector');
      }
    } catch (err) {
      console.error('Logout error:', err);
    }
  };

  // Check for existing session on mount
  useEffect(() => {
    const token = localStorage.getItem('squatter_session_token');
    if (token) {
      fetch(`${API_BASE}/games/session/validate`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(res => {
          if (!res.ok) throw new Error('Invalid session');
          return res.json();
        })
        .then(async data => {
          setSessionToken(token);
          setGameId(data.game_id);
          setGameCode(data.game_code);
          setUserId(data.user_id);
          setIsHost(data.is_host);

          if (data.game_status === 'suspended') {
            await fetch(`${API_BASE}/games/${data.game_id}/login`, {
              method: 'POST',
              headers: { 'Authorization': `Bearer ${token}` }
            });
          }

          if (data.game_status === 'lobby' || data.game_status === 'rolling_for_order') {
            setScreen('lobby');
          } else if (data.game_status === 'in_progress' || data.game_status === 'suspended') {
            setScreen('game');
          } else {
            localStorage.removeItem('squatter_session_token');
            setScreen('selector');
          }
        })
        .catch(() => {
          localStorage.removeItem('squatter_session_token');
          setScreen('selector');
        });
    } else {
      setScreen('selector');
    }
  }, []);

  const fetchGameState = useCallback(async () => {
    if (!gameId) return;

    // Coalesce calls fired within 250ms — multiple SSE events + onResolved often
    // arrive nearly simultaneously and would otherwise restart the in-flight
    // refresh, costing a round-trip each time.
    const now = Date.now();
    if (lastFetchRef.current && now - lastFetchRef.current < 250) {
      pendingFetchRef.current = true;
      return;
    }
    lastFetchRef.current = now;
    pendingFetchRef.current = false;

    if (fetchAbortControllerRef.current) {
      fetchAbortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    fetchAbortControllerRef.current = abortController;

    const headers = sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {};

    try {
      const [gameRes, ledgerRes, balancesRes, stationsRes, ramsRes, cardsRes, lastCardRes, pendingRes, tradeRes, diceRes] = await Promise.all([
        fetch(`${API_BASE}/games/${gameId}`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/ledger`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/player_balances`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/stations`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/stud-rams`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/player_retained_cards`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/last_drawn_card`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/pending-action`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/trades/active`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/dice_rolls`, { headers, signal: abortController.signal }),
      ]);

      if (!gameRes.ok) throw new Error(`Failed to load game: ${gameRes.status}`);

      const gameData = await gameRes.json();
      const ledgerData = ledgerRes.ok ? await ledgerRes.json() : [];
      const balancesData = balancesRes.ok ? await balancesRes.json() : {};
      const stationsData = stationsRes.ok ? await stationsRes.json() : {};
      const ramsData = ramsRes.ok ? await ramsRes.json() : [];
      const cardsData = cardsRes.ok ? await cardsRes.json() : {};
      const lastCardData = lastCardRes.ok ? await lastCardRes.json() : null;
      const pendingData = pendingRes.ok ? await pendingRes.json() : { pending_action: null };
      const tradeData = tradeRes.ok ? await tradeRes.json() : { trade: null };
      const diceData = diceRes.ok ? await diceRes.json() : { rolls: [] };

      setGame(gameData);
      setLedger(Array.isArray(ledgerData) ? ledgerData : []);
      setPlayerBalances(balancesData);
      setStations(stationsData);
      setStudRams(ramsData);
      setPlayerRetainedCards(cardsData);
      setLastDrawnCard(lastCardData);
      setPendingAction(pendingData.pending_action);
      setActiveTrade(tradeData.trade);
      setHoldingsRefreshKey((k) => k + 1);

      const rolls = diceData.rolls || [];
      setDiceRolls(rolls);
      if (rolls.length > 0) {
        const latest = rolls[0];
        setLastDiceRoll({
          dice_roll_1: latest.dice1,
          dice_roll_2: latest.dice2,
          total_roll: latest.total,
          is_double: latest.is_double,
          player_id: latest.player_id
        });
      }

      setError(null);
    } catch (err) {
      if (err.name === 'AbortError') return;
      throw err;
    } finally {
      // If a coalesced fetch was requested while we were running, run one more
      // to capture the latest state.
      if (pendingFetchRef.current) {
        pendingFetchRef.current = false;
        setTimeout(() => fetchGameStateRef.current && fetchGameStateRef.current(), 50);
      }
    }
  }, [gameId, sessionToken]);

  // Keep a ref to the latest fetchGameState for the coalesce-and-retry path.
  useEffect(() => { fetchGameStateRef.current = fetchGameState; }, [fetchGameState]);

  // Optimistic-resolution helper: clears the pending modal *immediately* so the
  // user sees instant feedback after a button press, then triggers a normal
  // backfill (debounced via fetchGameState).
  const handleResolved = useCallback(() => {
    setPendingAction(null);
    fetchGameState();
  }, [fetchGameState]);

  useEffect(() => {
    if (screen !== 'game' || !gameId) return;

    setLoading(true);
    fetchGameState()
      .catch((err) => {
        setError(err.message);
        setGame(null);
      })
      .finally(() => setLoading(false));

    const pollInterval = setInterval(() => {
      if (animatingPlayersRef.current.size === 0) {
        fetchGameState();
      }
    }, 5000);

    return () => clearInterval(pollInterval);
  }, [screen, gameId, sessionToken, fetchGameState]);

  // Animate token movement
  const animateTokenMovement = useCallback(async (playerId, startPosition, diceTotal) => {
    const BOARD_SIZE = 44;
    const STEP_DELAY = 280;

    animatingPlayersRef.current = new Set([...animatingPlayersRef.current, playerId]);
    setAnimatingPlayers(prev => new Set([...prev, playerId]));

    for (let step = 1; step <= diceTotal; step++) {
      await new Promise(resolve => setTimeout(resolve, STEP_DELAY));
      const newPosition = (startPosition + step) % BOARD_SIZE;
      setAnimatedPositions(prev => ({ ...prev, [playerId]: newPosition }));
    }

    animatingPlayersRef.current = new Set([...animatingPlayersRef.current].filter(id => id !== playerId));
    setAnimatingPlayers(prev => new Set([...prev].filter(id => id !== playerId)));
  }, []);

  // Handle real-time game events
  const handleGameEvent = useCallback((eventType, data) => {
    switch (eventType) {
      case 'turn_played':
        if (data.dice_roll && data.dice_roll.length === 2) {
          setLastDiceRoll({
            dice_roll_1: data.dice_roll[0],
            dice_roll_2: data.dice_roll[1],
            total_roll: data.dice_roll[0] + data.dice_roll[1],
            is_double: data.is_double,
            player_id: data.player_id
          });

          const diceTotal = data.dice_roll[0] + data.dice_roll[1];
          const movingPlayer = game?.players?.find(p => p.game_player_id === data.player_id);

          if (movingPlayer && diceTotal > 0) {
            const startPosition = movingPlayer.current_space_id;
            animateTokenMovement(data.player_id, startPosition, diceTotal).then(() => {
              if (data.pending_action) setPendingAction(data.pending_action);
              if (data.new_position !== undefined) {
                setGame(prev => prev ? {
                  ...prev,
                  players: prev.players.map(p =>
                    p.game_player_id === data.player_id
                      ? { ...p, current_space_id: data.new_position }
                      : p
                  )
                } : prev);
              }
              setAnimatedPositions(prev => {
                const next = { ...prev };
                delete next[data.player_id];
                return next;
              });
              fetchGameState();
            });
          } else {
            if (data.pending_action) setPendingAction(data.pending_action);
            fetchGameState();
          }
        } else {
          if (data.pending_action) setPendingAction(data.pending_action);
          fetchGameState();
        }
        break;
      case 'game_state_changed':
      case 'trade_initiated':
      case 'trade_status_changed':
      case 'trade_offer_updated':
      case 'trade_cancelled':
      case 'trade_executed':
        fetchGameState();
        break;
      case 'game_over':
        setGameOver(true);
        setWinner(data.winner_name);
        fetchGameState();
        break;
      default:
        break;
    }
  }, [fetchGameState, game, animateTokenMovement]);

  useGameEvents(
    screen === 'game' ? gameId : null,
    screen === 'game' ? sessionToken : null,
    handleGameEvent
  );

  const nextTurn = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/turns`, {
        method: "POST",
        headers: sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {}
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed: ${response.status}`);
      }
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

  // Game screen
  if (loading && !game) return <div>Loading...</div>;
  if (error) return <div style={{ color: "red" }}>Error: {error}</div>;
  if (!game) return <div>Loading game...</div>;

  const currentUserPlayer = game.players?.find(p => p.user_id === userId);
  const isCurrentPlayer = currentUserPlayer && currentUserPlayer.game_player_id === game.current_player_id;
  const isMissingTurn = isCurrentPlayer && (currentUserPlayer?.visiting_town_turns || 0) > 0;

  return (
    <div style={{ padding: "0.5rem 1rem", fontFamily: "sans-serif", position: "relative" }}>
      {/* Logout */}
      <button onClick={handleLogout} style={{
        position: "fixed", top: "1rem", right: "1rem",
        padding: "0.6rem 1.2rem", background: "#dc3545", color: "white",
        border: "none", borderRadius: "8px", fontSize: "0.9rem", fontWeight: "bold",
        cursor: "pointer", zIndex: Z_INDEX.LOGOUT_BUTTON
      }}>Logout</button>

      {/* Suspended Notice */}
      {game.status === 'suspended' && (
        <SuspendedGameNotice gameId={gameId} sessionToken={sessionToken} />
      )}

      <div style={{ display: "flex", gap: "2rem", justifyContent: "center", alignItems: "flex-start", maxWidth: 2000, margin: "0 auto" }}>
        {/* Left: Board */}
        <div style={{ flexShrink: 0, position: "relative", width: 1130, height: 1130 }}>
          <h1 style={{
            position: "absolute", top: "200px", left: "50%", transform: "translateX(-50%)",
            margin: 0, fontSize: "1.4rem", textAlign: "center", zIndex: 2, color: "#2d5016"
          }}>
            Squatter - {currentUserPlayer?.player_name || 'Player'}
          </h1>
          {gameCode && (
            <div style={{
              position: "absolute", top: "235px", left: "50%", transform: "translateX(-50%)",
              background: "rgba(255,255,255,0.9)", padding: "6px 14px", borderRadius: 6,
              boxShadow: "0 1px 4px rgba(0,0,0,0.1)", zIndex: 2, maxWidth: 360,
              textAlign: "center", fontSize: "0.85rem", color: "#2d5016"
            }}>
              The Current Game Code is <strong style={{ letterSpacing: "1px" }}>{gameCode}</strong>.
              <div style={{ fontSize: "0.75rem", color: "#555", marginTop: 2 }}>
                Use this code to rejoin the game.
              </div>
            </div>
          )}
          <Board
            players={game.players || []}
            currentPlayerId={game.current_player_id}
            animatedPositions={animatedPositions}
          />

          {/* Winner banner — spans the board horizontally.
              Triggers on either the game_over SSE event OR a game_won
              pending action, since the backend only creates the latter. */}
          {(() => {
            const gameWonPending = pendingAction?.action_type === 'game_won' ? pendingAction : null;
            const winnerName = winner || gameWonPending?.action_data?.winner_name;
            const showBanner = (gameOver || !!gameWonPending) && !!winnerName;
            if (!showBanner) return null;
            return (
              <div style={{
                position: "absolute", top: "50%", left: 0, right: 0,
                transform: "translateY(-50%)", zIndex: Z_INDEX.GAME_OVER,
                background: "linear-gradient(135deg, #ff6f00 0%, #ffb300 50%, #ff6f00 100%)",
                border: "6px double #fff", boxShadow: "0 8px 32px rgba(0,0,0,0.45)",
                padding: "1.4rem 1rem", textAlign: "center",
              }}>
                <div style={{
                  fontSize: "2.8rem", fontWeight: 900, color: "#fff",
                  textShadow: "2px 3px 8px rgba(0,0,0,0.5)", letterSpacing: 2,
                  fontFamily: "'Georgia', serif",
                }}>
                  {winnerName} is WINNER!!!!
                </div>
                <div style={{ fontSize: "0.95rem", color: "#fff8e1", marginTop: 6, fontStyle: "italic" }}>
                  6,000 sheep on a fully irrigated farm
                </div>
                <button onClick={async () => {
                  // Resolve the lingering pending action if present so future joiners don't see it.
                  if (gameWonPending) {
                    try {
                      await fetch(`${API_BASE}/games/${gameId}/decisions/acknowledge`, {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${sessionToken}` },
                      });
                    } catch (_) {}
                  }
                  setGameOver(false); setWinner(null); setScreen('selector');
                }}
                  style={{
                    marginTop: 12, padding: "0.6rem 1.4rem", background: "#fff",
                    color: "#ff6f00", border: "none", borderRadius: 8,
                    fontSize: "1rem", fontWeight: "bold", cursor: "pointer",
                  }}>
                  Return to Menu
                </button>
              </div>
            );
          })()}
          {/* Last Tucker Bag card */}
          {lastDrawnCard && (
            <div style={{
              position: "absolute", top: "300px", left: "50%", transform: "translateX(-50%)",
              background: "rgba(255,255,255,0.95)", padding: "12px 18px", borderRadius: 8,
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)", zIndex: 2, maxWidth: 350, textAlign: "center"
            }}>
              <h4 style={{ margin: "0 0 4px", color: "#6a4c93", fontSize: "0.9rem" }}>Tucker Bag</h4>
              <p style={{ margin: 0, fontSize: "0.8rem", fontWeight: "bold" }}>{lastDrawnCard.title}</p>
              <p style={{ margin: "4px 0 0", fontSize: "0.75rem", color: "#555" }}>{lastDrawnCard.body_text}</p>
            </div>
          )}

          {/* Stock Sale card overlay — anchored to the board, below "Squatter".
              Renders for any pending action whose data carries a Stock Sale
              card snapshot (stock_sale_result, tucker_bag_result with card,
              drought_effect with haystack-drawn card, etc.). */}
          {(() => {
            if (!pendingAction) return null;
            const sd = pendingAction.action_data || {};
            const at = pendingAction.action_type;
            const overlayTypes = ['stock_sale_result', 'tucker_bag_result', 'drought_effect'];
            const hasCard = !!(sd.card || sd.stock_card_used);
            if (!overlayTypes.includes(at) || !hasCard) return null;

            const card = sd.card || sd.stock_card_used || {};
            const isStockResult = at === 'stock_sale_result';
            const isBuy = sd.action === 'buy';
            const activeIsMe = (game?.players || []).some(
              p => p.game_player_id === pendingAction.active_player_id && p.user_id === userId
            );
            const activeName = (game?.players || []).find(
              p => p.game_player_id === pendingAction.active_player_id
            )?.player_name;
            const ackUrl = `${API_BASE}/games/${gameId}/decisions/acknowledge`;
            const onOk = async () => {
              try {
                await fetch(ackUrl, {
                  method: 'POST',
                  headers: { 'Authorization': `Bearer ${sessionToken}`, 'Content-Type': 'application/json' },
                });
                setPendingAction(null);
                fetchGameState();
              } catch (e) { /* surfacing handled by next poll */ }
            };
            const titleByType = {
              stock_sale_result: 'Stock Sale — Card Revealed',
              tucker_bag_result: `${sd.card_title || 'Tucker Bag'} — Stock Sale Card`,
              drought_effect: 'Local Drought — Stock Sale Card (Haystack)',
            };
            return (
              <div style={{
                position: "absolute", top: "600px", left: "50%", transform: "translateX(-50%)",
                background: "#fff", border: "2px solid #1982c4", borderRadius: 10,
                padding: "14px 18px", boxShadow: "0 4px 12px rgba(0,0,0,0.2)", zIndex: 3,
                width: 360,
              }}>
                <h3 style={{ margin: "0 0 8px", color: "#1982c4", fontSize: "1rem", textAlign: "center" }}>
                  {titleByType[at] || 'Stock Sale Card'}
                </h3>
                <div style={{ padding: "8px", background: "#E3F2FD", borderRadius: 6, fontSize: "0.85rem" }}>
                  <table style={{ width: "100%" }}>
                    <tbody>
                      {card.buy_price_per_pen !== undefined && (
                        <tr><td>Buy</td><td style={{ textAlign: "right" }}><strong>${card.buy_price_per_pen}/pen</strong></td></tr>
                      )}
                      <tr><td>Sell — Natural</td><td style={{ textAlign: "right" }}><strong>${card.sell_price_natural}/pen</strong></td></tr>
                      <tr><td>Sell — Improved/Irrigated</td><td style={{ textAlign: "right" }}><strong>${card.sell_price_improved_irrigated}/pen</strong></td></tr>
                    </tbody>
                  </table>
                </div>
                <div style={{ marginTop: 8, padding: "8px", background: "#F1F8E9", borderRadius: 6, fontSize: "0.85rem" }}>
                  {isStockResult ? (
                    isBuy ? (
                      <>Bought <strong>{sd.pens}</strong> pens at <strong>${sd.buy_price}/pen</strong> = <strong>${sd.total_cost}</strong></>
                    ) : (
                      <>Sold <strong>{sd.pens}</strong> pens for <strong>${sd.total_income}</strong>
                        {Array.isArray(sd.tiers) && sd.tiers.some(([, n]) => n > 0) && (
                          <div style={{ fontSize: "0.78rem", color: "#666", marginTop: 4 }}>
                            {sd.tiers.filter(([, n]) => n > 0).map(([t, n]) => `${n} ${t}`).join(', ')}
                          </div>
                        )}
                      </>
                    )
                  ) : (
                    <>Sold <strong>{sd.pens_sold}</strong> pens for <strong>${sd.income}</strong>
                      {sd.by_type && (
                        <div style={{ fontSize: "0.78rem", color: "#666", marginTop: 4 }}>
                          {Object.entries(sd.by_type).filter(([, n]) => n > 0).map(([t, n]) => `${n} ${t}`).join(', ')}
                        </div>
                      )}
                      {sd.haystack_lost && (
                        <div style={{ fontSize: "0.78rem", color: "#b71c1c", marginTop: 4 }}>
                          Haystack lost (returned to Bank).
                        </div>
                      )}
                      {sd.restock_blocked && (
                        <div style={{ fontSize: "0.78rem", color: "#E65100", marginTop: 4, fontWeight: "bold" }}>
                          Restock blocked until full circuit.
                        </div>
                      )}
                    </>
                  )}
                </div>
                {activeIsMe && (
                  <div style={{ textAlign: "center", marginTop: 10 }}>
                    <button onClick={onOk} style={{
                      padding: "0.5rem 1.2rem", background: "#1982c4", color: "#fff",
                      border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold"
                    }}>OK</button>
                  </div>
                )}
                {!activeIsMe && (
                  <p style={{ fontSize: "0.78rem", color: "#666", textAlign: "center", margin: "8px 0 0", fontStyle: "italic" }}>
                    Waiting for {activeName}...
                  </p>
                )}
              </div>
            );
          })()}

          {/* Tucker Bag draw — anchored to the board, below "Squatter" */}
          {pendingAction && pendingAction.action_type === 'tucker_bag_drawn' && (() => {
            const sd = pendingAction.action_data || {};
            const activeIsMe = (game?.players || []).some(
              p => p.game_player_id === pendingAction.active_player_id && p.user_id === userId
            );
            const activeName = (game?.players || []).find(
              p => p.game_player_id === pendingAction.active_player_id
            )?.player_name;
            const tbUrl = `${API_BASE}/games/${gameId}/decisions/tucker-bag`;
            const buyHsUrl = `${API_BASE}/games/${gameId}/station/buy-haystack`;
            const post = async (url, body) => {
              try {
                await fetch(url, {
                  method: 'POST',
                  headers: { 'Authorization': `Bearer ${sessionToken}`, 'Content-Type': 'application/json' },
                  body: JSON.stringify(body || {}),
                });
                setPendingAction(null);
                fetchGameState();
              } catch (e) { /* surfacing handled by next poll */ }
            };
            return (
              <div style={{
                position: "absolute", top: "600px", left: "50%", transform: "translateX(-50%)",
                background: "#fff", border: "2px solid #6a4c93", borderRadius: 10,
                padding: "14px 18px", boxShadow: "0 4px 12px rgba(0,0,0,0.2)", zIndex: 3,
                width: 380,
              }}>
                <h3 style={{ margin: "0 0 4px", color: "#6a4c93", fontSize: "1rem", textAlign: "center" }}>
                  Tucker Bag
                </h3>
                <h4 style={{ margin: "0 0 6px", textAlign: "center" }}>{sd.title}</h4>
                <p style={{ color: "#555", lineHeight: 1.4, fontSize: "0.85rem", margin: 0 }}>{sd.body_text}</p>
                {sd.tax_breakdown && (
                  <div style={{ marginTop: "0.6rem", padding: "0.6rem", background: "#f5f5f5", borderRadius: 6, border: "1px solid #ddd" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                      <tbody>
                        {sd.tax_breakdown.lines.map((line, i) => (
                          <tr key={i}>
                            <td style={{ padding: "0.2rem 0" }}>{line.label}</td>
                            <td style={{ padding: "0.2rem 0.5rem", color: "#666", textAlign: "right" }}>
                              {line.rate_label || `@ $${line.rate}`}
                            </td>
                            <td style={{ padding: "0.2rem 0", textAlign: "right", fontWeight: 500 }}>${line.amount.toLocaleString()}</td>
                          </tr>
                        ))}
                        <tr style={{ borderTop: "2px solid #999" }}>
                          <td colSpan={2} style={{ padding: "0.3rem 0", fontWeight: "bold" }}>Total Tax</td>
                          <td style={{ padding: "0.3rem 0", textAlign: "right", fontWeight: "bold", color: "#d32f2f" }}>
                            ${sd.tax_breakdown.total.toLocaleString()}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}
                {sd.is_retainable && (
                  <p style={{ color: "#4caf50", fontWeight: "bold", fontSize: "0.85rem", marginTop: "0.5rem" }}>
                    This card can be kept!
                  </p>
                )}
                {sd.haystack_available && (
                  <div style={{ marginTop: "0.5rem", padding: "0.6rem", background: "#F1F8E9", border: "1px solid #7CB342", borderRadius: 6, fontSize: "0.82rem", display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                    <div style={{ flex: 1 }}>
                      <strong style={{ color: "#33691E" }}>Haymaking Season!</strong>{" "}
                      Haystack available for ${sd.haystack_cost}
                      {sd.haystack_drought_premium && (
                        <span style={{ marginLeft: 6, color: "#b71c1c", fontSize: "0.78rem" }}>(drought premium)</span>
                      )}
                    </div>
                    {activeIsMe && (
                      <button onClick={() => post(buyHsUrl, {})} style={{
                        padding: "0.4rem 0.9rem", background: "#7CB342", color: "#fff",
                        border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold", fontSize: "0.82rem"
                      }}>Buy Haystack (${sd.haystack_cost})</button>
                    )}
                  </div>
                )}
                {activeIsMe && (
                  <div style={{ display: "flex", gap: "0.5rem", marginTop: 10, flexWrap: "wrap", justifyContent: "center" }}>
                    {sd.is_retainable && sd.purchase_price > 0 ? (
                      <>
                        <button onClick={() => post(tbUrl, { buy_card: true })} style={{
                          padding: "0.5rem 1.2rem", background: "#4caf50", color: "#fff",
                          border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold"
                        }}>Buy (${sd.purchase_price})</button>
                        <button onClick={() => post(tbUrl, { buy_card: false })} style={{
                          padding: "0.5rem 1.2rem", background: "#666", color: "#fff",
                          border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold"
                        }}>Decline</button>
                      </>
                    ) : (
                      <button onClick={() => post(tbUrl, { buy_card: !!sd.is_retainable })} style={{
                        padding: "0.5rem 1.2rem", background: "#6a4c93", color: "#fff",
                        border: "none", borderRadius: 6, cursor: "pointer", fontWeight: "bold"
                      }}>{sd.is_retainable ? 'Keep Card' : 'OK'}</button>
                    )}
                  </div>
                )}
                {!activeIsMe && (
                  <p style={{ fontSize: "0.78rem", color: "#666", textAlign: "center", margin: "8px 0 0", fontStyle: "italic" }}>
                    Waiting for {activeName}...
                  </p>
                )}
              </div>
            );
          })()}
        </div>

        {/* Right: Controls and player info */}
        <div style={{ flex: 1, minWidth: 420, maxWidth: 550, position: "sticky", top: 20 }}>
          {/* Action buttons */}
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            <button onClick={() => setShowStationPanel(true)} style={{
              padding: "0.5rem 1rem", background: "#4caf50", color: "#fff",
              border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem"
            }}>Station</button>
            <button onClick={() => setShowTradingBoard(true)} style={{
              padding: "0.5rem 1rem", background: "#6a4c93", color: "#fff",
              border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem"
            }}>Trade</button>
            <button onClick={nextTurn} disabled={isSubmitting || pendingAction || !isCurrentPlayer} style={{
              padding: "0.5rem 1rem",
              background: (isSubmitting || pendingAction || !isCurrentPlayer) ? "#ccc" : "#1982c4",
              color: "#fff", border: "none", borderRadius: "6px",
              cursor: (isSubmitting || pendingAction || !isCurrentPlayer) ? "not-allowed" : "pointer",
              fontSize: "0.9rem"
            }}>
              {isSubmitting ? (isMissingTurn ? "Missing Turn..." : "Rolling...") : pendingAction ? "Resolve Action" : !isCurrentPlayer
                ? `${game.players?.find(p => p.game_player_id === game.current_player_id)?.player_name || ''}'s Turn`
                : isMissingTurn ? "Miss Turn" : "Roll Dice"}
            </button>
          </div>

          {/* Dice display */}
          {lastDiceRoll && (
            <div style={{ marginBottom: "1rem", padding: "10px 14px", background: "#fff", borderRadius: 8, border: "2px solid #1982c4" }}>
              <span style={{ fontWeight: "bold" }}>Last Roll: </span>
              <span style={{ fontSize: "1.1rem", fontWeight: "bold" }}>{lastDiceRoll.dice_roll_1}</span>
              <span> + </span>
              <span style={{ fontSize: "1.1rem", fontWeight: "bold" }}>{lastDiceRoll.dice_roll_2}</span>
              <span> = </span>
              <span style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#1982c4" }}>{lastDiceRoll.total_roll}</span>
              {lastDiceRoll.is_double && <span style={{ marginLeft: "0.5rem", color: "#ff6b6b", fontWeight: "bold" }}>DOUBLE!</span>}
            </div>
          )}

          {/* Player list */}
          <h2 style={{ margin: "0 0 0.5rem" }}>Players</h2>
          <ul style={{ paddingLeft: "1rem", listStyle: "none" }}>
            {game.players?.map((p) => {
              const spaceLabel = SPACE_LABELS[p.current_space_id] || `Space ${p.current_space_id}`;
              const cash = playerBalances[String(p.game_player_id)] ?? "?";
              const station = stations[String(p.game_player_id)] || stations[p.game_player_id];
              const totalPens = station?.total_pens ?? "?";
              const retained = playerRetainedCards[p.game_player_id] || [];
              const isCurrent = p.game_player_id === game.current_player_id;

              return (
                <li key={p.game_player_id} style={{
                  marginBottom: 10, padding: "10px", borderRadius: "8px",
                  background: isCurrent ? "linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)" : "transparent",
                  border: isCurrent ? "2px solid #4caf50" : "1px solid #e0e0e0"
                }}>
                  <div
                    onClick={() => setViewingPlayerId(p.game_player_id)}
                    title="Click to view this player's station"
                    style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap", cursor: "pointer" }}
                  >
                    <strong style={{ textDecoration: "underline dotted", textUnderlineOffset: 3 }}>{p.player_name}</strong>
                    <span style={{ fontSize: "0.85rem", color: "#555" }}>{spaceLabel}</span>
                    <span style={{ fontSize: "0.85rem", color: "#1982c4" }}>${cash}</span>
                    <span style={{ fontSize: "0.85rem", color: "#4caf50" }}>{totalPens} pens</span>
                    {p.is_in_drought && <span style={{ fontSize: "0.8rem", color: "#d32f2f" }}>DROUGHT</span>}
                    {p.visiting_town_turns > 0 && <span style={{ fontSize: "0.8rem", color: "#ff9800" }}>Town ({p.visiting_town_turns})</span>}
                    {p.has_haystack && <span style={{ fontSize: "0.8rem", color: "#795548" }}>Haystack</span>}
                  </div>
                  {retained.length > 0 && (
                    <div style={{ fontSize: "0.8rem", color: "#6a4c93", marginTop: "4px" }}>
                      Cards: {retained.map((card, i) => (
                        <button key={i} onClick={(e) => { e.stopPropagation(); setSelectedCard(card); }} style={{
                          background: 'none', border: 'none', color: '#6a4c93',
                          textDecoration: 'underline', cursor: 'pointer', padding: 0, font: 'inherit'
                        }}>{card.title}{i < retained.length - 1 ? ", " : ""}</button>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>

          {/* Stud Rams */}
          {studRams.length > 0 && (
            <div style={{ marginTop: "1rem", background: "#fff", padding: "10px", borderRadius: 8, border: "1px solid #ddd" }}>
              <h3 style={{ margin: "0 0 6px", fontSize: "1rem" }}>Stud Rams</h3>
              {studRams.map(ram => (
                <div key={ram.space_id} style={{ fontSize: "0.8rem", marginBottom: 3 }}>
                  <span style={{ fontWeight: "bold" }}>{ram.space_name}</span>
                  {" - "}
                  {ram.owner_game_player_id
                    ? <span style={{ color: "#4caf50" }}>{game.players?.find(p => p.game_player_id === ram.owner_game_player_id)?.player_name}</span>
                    : <span style={{ color: "#999" }}>Available (${ram.purchase_price})</span>
                  }
                  <span style={{ color: "#666" }}> Fee: ${ram.stud_fee}</span>
                </div>
              ))}
            </div>
          )}

          {/* Ledger */}
          <div style={{ marginTop: "1.5rem", background: "#fff", padding: "10px", borderRadius: 8, border: "1px solid #ddd", maxHeight: 300, overflowY: "auto" }}>
            <h3 style={{ margin: "0 0 6px", fontSize: "1rem" }}>Ledger</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #ccc" }}>
                  <th align="left">Type</th><th align="left">Amount</th><th align="left">From</th><th align="left">To</th>
                </tr>
              </thead>
              <tbody>
                {ledger.slice(0, 10).map((txn) => (
                  <tr key={txn.id} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={{ padding: "4px 2px" }}>{txn.type}</td>
                    <td style={{ padding: "4px 2px" }}>${txn.amount}</td>
                    <td style={{ padding: "4px 2px" }}>{txn.from}</td>
                    <td style={{ padding: "4px 2px" }}>{txn.to}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Dice Roll Register */}
          <div style={{ marginTop: "1rem", background: "#fff", padding: "10px", borderRadius: 8, border: "1px solid #ddd", maxHeight: 250, overflowY: "auto" }}>
            <h3 style={{ margin: "0 0 6px", fontSize: "1rem" }}>Dice Rolls</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #ccc" }}>
                  <th align="left">#</th><th align="left">Who</th><th align="left">Dice</th><th align="left">To</th>
                </tr>
              </thead>
              <tbody>
                {diceRolls.map((roll) => (
                  <tr key={roll.roll_number} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={{ padding: "4px 2px" }}>{roll.roll_number}</td>
                    <td style={{ padding: "4px 2px" }}>{roll.player}</td>
                    <td style={{ padding: "4px 2px" }}>{roll.dice1}+{roll.dice2}={roll.total}</td>
                    <td style={{ padding: "4px 2px" }}>{roll.to_location ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Far right: Holdings (cards + stud rams + status) */}
        {currentUserPlayer && (
          <HoldingsPanel
            gameId={gameId}
            playerId={currentUserPlayer.game_player_id}
            refreshKey={holdingsRefreshKey}
            onCardClick={(card) => setSelectedCard(card)}
          />
        )}
      </div>

      {/* Pending Action Modal */}
      {animatingPlayers.size === 0 && pendingAction && (
        <PendingActionModal
          gameId={gameId}
          sessionToken={sessionToken}
          userId={userId}
          pendingAction={pendingAction}
          players={game.players || []}
          onResolved={handleResolved}
          activePlayerHasHighStockPrices={
            (playerRetainedCards[pendingAction.active_player_id] || [])
              .some(c => c.title === 'High Stock Prices')
          }
        />
      )}

      {/* Station Panel */}
      {showStationPanel && (
        <StationPanel
          gameId={gameId}
          sessionToken={sessionToken}
          onClose={() => setShowStationPanel(false)}
          onUpdate={fetchGameState}
          isMyTurn={isCurrentPlayer}
        />
      )}

      {/* Trading Board */}
      {showTradingBoard && (
        <div style={{
          position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
          width: "800px", maxHeight: "80vh", overflowY: "auto",
          background: "#fff", border: "3px solid #6a4c93", borderRadius: "12px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.3)", zIndex: Z_INDEX.PANEL
        }}>
          <TradingBoard
            gameId={gameId}
            sessionToken={sessionToken}
            userId={userId}
            game={game}
            playerBalances={playerBalances}
            allPlayerAssets={{}}
            playerRetainedCards={playerRetainedCards}
            activeTradeFromParent={activeTrade}
            onClose={() => setShowTradingBoard(false)}
          />
        </div>
      )}

{/* Player Station Modal — click any player in the list */}
      {viewingPlayerId !== null && (
        <PlayerStationModal
          gameId={gameId}
          playerId={viewingPlayerId}
          playerName={game.players?.find(p => p.game_player_id === viewingPlayerId)?.player_name}
          onClose={() => setViewingPlayerId(null)}
          onCardClick={(card) => setSelectedCard(card)}
        />
      )}

      {/* Retained Card Popup */}
      {selectedCard && (
        <RetainedCardPopup card={selectedCard} onClose={() => setSelectedCard(null)} />
      )}

    </div>
  );
}

export default App;
