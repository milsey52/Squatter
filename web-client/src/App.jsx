import { useEffect, useState, useCallback, useRef } from "react";
import Board from "./Board";
import GameSelector from "./components/GameSelector";
import GameLobby from "./components/GameLobby";
import SuspendedGameNotice from "./components/SuspendedGameNotice";
import RetainedCardPopup from "./components/RetainedCardPopup";
import HoldingsPanel from "./components/HoldingsPanel";
import StationPanel from "./components/StationPanel";
import PendingActionModal from "./components/PendingActionModal";
import PlayerStationModal from "./components/PlayerStationModal";
import PlayerList from "./components/PlayerList";
import DebtBanner from "./components/DebtBanner";
import WinnerBanner from "./components/WinnerBanner";
import { StockSaleCardOverlay, TuckerBagDrawOverlay } from "./components/BoardOverlays";
import { useGameEvents } from "./hooks/useGameEvents";
import { Z_INDEX } from "./constants/zIndex";
import { useTheme } from "./theme";
import SettingsModal, { SettingsButton } from "./components/SettingsModal";

const API_BASE = import.meta.env.VITE_API_BASE || '';

function App() {
  const { theme } = useTheme();
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
  // Non-fatal action feedback (refused roll etc.) shown as a toast.
  const [actionError, setActionError] = useState(null);
  const actionErrorTimer = useRef(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastDiceRoll, setLastDiceRoll] = useState(null);
  // AI "thinking out loud" narration, shown during its pacing pause.
  const [aiThinking, setAiThinking] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [showStationPanel, setShowStationPanel] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);
  const [viewingPlayerId, setViewingPlayerId] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [holdingsRefreshKey, setHoldingsRefreshKey] = useState(0);
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
      const [gameRes, ledgerRes, balancesRes, stationsRes, ramsRes, cardsRes, lastCardRes, pendingRes, diceRes] = await Promise.all([
        fetch(`${API_BASE}/games/${gameId}`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/ledger`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/player_balances`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/stations`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/stud-rams`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/player_retained_cards`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/last_drawn_card`, { headers, signal: abortController.signal }),
        fetch(`${API_BASE}/games/${gameId}/pending-action`, { headers, signal: abortController.signal }),
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
      const diceData = diceRes.ok ? await diceRes.json() : { rolls: [] };

      setGame(gameData);
      setLedger(Array.isArray(ledgerData) ? ledgerData : []);
      setPlayerBalances(balancesData);
      setStations(stationsData);
      setStudRams(ramsData);
      setPlayerRetainedCards(cardsData);
      setLastDrawnCard(lastCardData);
      setPendingAction(pendingData.pending_action);
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
    // Pin the token to its start square SYNCHRONOUSLY. Without this there
    // is a one-step-delay window where the Board falls back to the player's
    // state position — and if an in-flight refresh just wrote the server's
    // new position, the token flashes at the destination before walking.
    setAnimatedPositions(prev => ({ ...prev, [playerId]: startPosition }));

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
      case 'ai_thinking':
        // Narration shown during the AI's pacing pause. Cleared when the
        // action lands (turn_played / game_state_changed below).
        setAiThinking({ playerName: data.player_name, text: data.text });
        break;
      case 'turn_played':
        setAiThinking(null);
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

          if (movingPlayer && diceTotal > 0 &&
              !animatingPlayersRef.current.has(data.player_id)) {
            // Derive the start square from the event itself (destination
            // minus the roll) — the client-side position may already have
            // been overwritten by a racing refresh.
            const BOARD_SIZE = 44;
            const startPosition = data.new_position !== undefined && data.new_position !== null
              ? ((data.new_position - diceTotal) % BOARD_SIZE + BOARD_SIZE) % BOARD_SIZE
              : movingPlayer.current_board_index;
            animateTokenMovement(data.player_id, startPosition, diceTotal).then(() => {
              if (data.pending_action) setPendingAction(data.pending_action);
              if (data.new_position !== undefined) {
                setGame(prev => prev ? {
                  ...prev,
                  players: prev.players.map(p =>
                    p.game_player_id === data.player_id
                      ? { ...p, current_board_index: data.new_position }
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
        setAiThinking(null);
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
      // Transient toast — a refused roll (debt, not your turn) must not
      // blank the game screen: the player needs the Station panel to
      // mortgage / sell their way out of debt.
      showActionError(err.message);
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

  // Show a transient toast (used by the debt banner and the roll handler).
  const showActionError = (msg) => {
    setActionError(msg);
    if (actionErrorTimer.current) clearTimeout(actionErrorTimer.current);
    actionErrorTimer.current = setTimeout(() => setActionError(null), 8000);
  };

  return (
    <div style={{ padding: "0.5rem 1rem", fontFamily: "sans-serif", position: "relative",
                  background: theme.pageBg, color: theme.text, minHeight: "100vh" }}>
      {/* Top-right controls: Settings + Logout */}
      <div style={{
        position: "fixed", top: "1rem", right: "1rem",
        display: "flex", gap: "0.5rem", alignItems: "center",
        zIndex: Z_INDEX.LOGOUT_BUTTON
      }}>
        <SettingsButton onClick={() => setShowSettings(true)} />
        <button onClick={handleLogout} style={{
          padding: "0.6rem 1.2rem", background: "#dc3545", color: "white",
          border: "none", borderRadius: "8px", fontSize: "0.9rem", fontWeight: "bold",
          cursor: "pointer",
        }}>Logout</button>
      </div>
      {showSettings && (
        <SettingsModal
          gameId={gameId}
          sessionToken={sessionToken}
          isHost={isHost}
          aiReactionTimeSeconds={game?.game_rules?.ai_reaction_time_seconds ?? 4}
          startingCash={game?.game_rules?.starting_cash ?? 2000}
          gameStatus={game?.status}
          onClose={() => setShowSettings(false)}
          onSettingsChanged={fetchGameState}
        />
      )}

      {/* Suspended Notice */}
      {game.status === 'suspended' && (
        <SuspendedGameNotice gameId={gameId} sessionToken={sessionToken} />
      )}

      {/* Action feedback toast (refused roll: debt, not your turn, ...) */}
      {actionError && (
        <div
          onClick={() => setActionError(null)}
          style={{
            position: "fixed", top: "4.5rem", left: "50%", transform: "translateX(-50%)",
            zIndex: 3000, maxWidth: 480, cursor: "pointer",
            background: "#b71c1c", color: "#fff", padding: "0.75rem 1.25rem",
            borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,0.35)",
            fontSize: "0.95rem", textAlign: "center",
          }}
        >
          {actionError}
        </div>
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

          {/* Winner banner + final standings table. */}
          <WinnerBanner
            gameId={gameId}
            sessionToken={sessionToken}
            pendingAction={pendingAction}
            winner={winner}
            gameOver={gameOver}
            zIndex={Z_INDEX.GAME_OVER}
            onReturnToMenu={() => { setGameOver(false); setWinner(null); setScreen('selector'); }}
          />
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

          <StockSaleCardOverlay
            gameId={gameId} sessionToken={sessionToken} userId={userId}
            pendingAction={pendingAction} players={game.players || []}
            onResolved={handleResolved}
          />
          <TuckerBagDrawOverlay
            gameId={gameId} sessionToken={sessionToken} userId={userId}
            pendingAction={pendingAction} players={game.players || []}
            onResolved={handleResolved}
          />
        </div>

        {/* Right: Controls and player info */}
        <div style={{ flex: 1, minWidth: 420, maxWidth: 550, position: "sticky", top: 20 }}>
          <DebtBanner
            gameId={gameId} sessionToken={sessionToken}
            currentUserPlayer={currentUserPlayer}
            playerBalances={playerBalances} stations={stations}
            pendingAction={pendingAction}
            onOpenStation={() => setShowStationPanel(true)}
            onRefresh={fetchGameState} onError={showActionError}
          />

          {/* Action buttons */}
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            <button onClick={() => setShowStationPanel(true)} style={{
              padding: "0.5rem 1rem", background: "#4caf50", color: "#fff",
              border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem"
            }}>Station</button>
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

          {/* AI thinking-out-loud — shown during the AI's pacing pause */}
          {aiThinking && (
            <div style={{
              marginBottom: "1rem", padding: "10px 14px", borderRadius: 8,
              background: "#ede7f6", border: "2px solid #6a4c93", color: "#4a328c",
              fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "0.5rem",
            }}>
              <span style={{ fontSize: "1.1rem" }}>🤖💭</span>
              <span><strong>{aiThinking.playerName}</strong> is thinking: <em>{aiThinking.text}</em></span>
            </div>
          )}

          {/* Dice display */}
          {lastDiceRoll && (
            <div style={{ marginBottom: "1rem", padding: "10px 14px", background: theme.panelBg, color: theme.text, borderRadius: 8, border: "2px solid #1982c4" }}>
              <span style={{ fontWeight: "bold" }}>Last Roll: </span>
              <span style={{ fontSize: "1.1rem", fontWeight: "bold" }}>{lastDiceRoll.dice_roll_1}</span>
              <span> + </span>
              <span style={{ fontSize: "1.1rem", fontWeight: "bold" }}>{lastDiceRoll.dice_roll_2}</span>
              <span> = </span>
              <span style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#1982c4" }}>{lastDiceRoll.total_roll}</span>
              {lastDiceRoll.is_double && <span style={{ marginLeft: "0.5rem", color: "#ff6b6b", fontWeight: "bold" }}>DOUBLE!</span>}
            </div>
          )}

          <PlayerList
            players={game.players || []}
            currentPlayerId={game.current_player_id}
            playerBalances={playerBalances} stations={stations}
            playerRetainedCards={playerRetainedCards}
            onViewPlayer={setViewingPlayerId}
            onCardClick={setSelectedCard}
          />

          {/* Stud Rams */}
          {studRams.length > 0 && (
            <div style={{ marginTop: "1rem", background: theme.panelBg, color: theme.text, padding: "10px", borderRadius: 8, border: `1px solid ${theme.panelBorder}` }}>
              <h3 style={{ margin: "0 0 6px", fontSize: "1rem" }}>Stud Rams</h3>
              {studRams.map(ram => (
                <div key={ram.space_id} style={{ fontSize: "0.8rem", marginBottom: 3 }}>
                  <span style={{ fontWeight: "bold" }}>{ram.space_name}</span>
                  {" - "}
                  {ram.owner_game_player_id
                    ? <span style={{ color: "#66bb6a" }}>{game.players?.find(p => p.game_player_id === ram.owner_game_player_id)?.player_name}</span>
                    : <span style={{ color: theme.textMuted }}>Available (${ram.purchase_price})</span>
                  }
                  <span style={{ color: theme.textMuted }}> Fee: ${ram.stud_fee}</span>
                </div>
              ))}
            </div>
          )}

          {/* Ledger */}
          <div style={{ marginTop: "1.5rem", background: theme.panelBg, color: theme.text, padding: "10px", borderRadius: 8, border: `1px solid ${theme.panelBorder}`, maxHeight: 300, overflowY: "auto" }}>
            <h3 style={{ margin: "0 0 6px", fontSize: "1rem" }}>Ledger</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${theme.panelBorderStrong}` }}>
                  <th align="left">Type</th><th align="left">Amount</th><th align="left">From</th><th align="left">To</th>
                </tr>
              </thead>
              <tbody>
                {ledger.slice(0, 10).map((txn) => (
                  <tr key={txn.id} style={{ borderBottom: `1px solid ${theme.divider}` }}>
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
          <div style={{ marginTop: "1rem", background: theme.panelBg, color: theme.text, padding: "10px", borderRadius: 8, border: `1px solid ${theme.panelBorder}`, maxHeight: 250, overflowY: "auto" }}>
            <h3 style={{ margin: "0 0 6px", fontSize: "1rem" }}>Dice Rolls</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${theme.panelBorderStrong}` }}>
                  <th align="left">#</th><th align="left">Who</th><th align="left">Dice</th><th align="left">To</th>
                </tr>
              </thead>
              <tbody>
                {diceRolls.map((roll) => (
                  <tr key={roll.roll_number} style={{ borderBottom: `1px solid ${theme.divider}` }}>
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

      {/* Pending Action Modal. The debtor's own debt_settlement gate is NOT
          shown as a modal — the red debt banner takes its place, because the
          debtor needs the Station panel (which a modal would cover) to sell
          their way out. Everyone else sees the modal ("waiting for X..."). */}
      {animatingPlayers.size === 0 && pendingAction &&
        !(pendingAction.action_type === 'debt_settlement' &&
          pendingAction.active_player_id === currentUserPlayer?.game_player_id) && (
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
          inDrought={!!currentUserPlayer?.is_in_drought}
        />
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
