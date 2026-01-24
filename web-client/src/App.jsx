import { useEffect, useState, useCallback } from "react";                                                                                                                              
import Board from "./Board";                                                                                                                                                           
                                                                                                                                                                                       
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
  const [gameId] = useState(1);                                                                                                                                                        
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
                                                                                                                                                                                       
  const fetchGameLedgerJackpot = useCallback(async () => {                                                                                                                             
    const [gameRes, ledgerRes, jackpotRes, balancesRes, assetsRes, cardsRes, lastDrawnCardsRes] = await Promise.all([                                                                                     
      fetch(`${API_BASE}/games/${gameId}`),                                                                                                                                            
      fetch(`${API_BASE}/games/${gameId}/ledger`),                                                                                                                                     
      fetch(`${API_BASE}/games/${gameId}/jackpot`),                                                                                                                                    
      fetch(`${API_BASE}/games/${gameId}/player_balances`),                                                                                                                            
      fetch(`${API_BASE}/games/${gameId}/player_assets`),                                                                                                                              
      fetch(`${API_BASE}/games/${gameId}/player_retained_cards`),                                                                                                                       
      fetch(`${API_BASE}/games/${gameId}/last_drawn_cards`)
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

    setGame(gameData); 
    setLedger(Array.isArray(ledgerData) ? ledgerData : []);                                                                                                                            
    setJackpot(jackpotData.jackpot);                                                                                                                                                   
    setPlayerBalances(balancesData);                                                                                                                                                   
    setAllPlayerAssets(assetsData);                                                                                                                                                    
    setPlayerRetainedCards(cardsData);
    setLastDrawnCards(lastDrawnCardsData);
    setError(null);                                                                                                                                                                    
  }, [gameId]);                                                                                                                                                                        
                                                                                                                                                                                       
  useEffect(() => {                                                                                                                                                                    
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
      })                                                                                                                                                                               
      .finally(() => setLoading(false));                                                                                                                                               
  }, [gameId, fetchGameLedgerJackpot]);                                                                                                                                                
                                                                                                                                                                                       
  const nextTurn = async () => {
    if (isSubmitting) return;

    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/turns`, { method: "POST" });
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
                                                                                                                                                                                       
  if (loading) return <div>Loading…</div>;
  if (error && error.includes("404")) {
    return (
      <div style={{
        padding: "2rem",
        textAlign: "center",
        fontFamily: "sans-serif",
        maxWidth: 500,
        margin: "4rem auto"
      }}>
        <h1 style={{ color: "#1982c4" }}>Monopoly Perth</h1>
        <p style={{ fontSize: "1.2rem", color: "#333" }}>
          No game has been started.
        </p>
        <p style={{ color: "#666" }}>
          Please start a new game using the CLI:
        </p>
        <code style={{
          display: "block",
          background: "#f5f5f5",
          padding: "1rem",
          borderRadius: "6px",
          marginTop: "1rem",
          fontSize: "0.9rem"
        }}>
          python cli.py start-game --players Alice Bob Charlie
        </code>
      </div>
    );
  }
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
        {/* Board + floating controls */}
        <div style={{ position: "relative", width: 1100, height: 1100 }}>                                                                                                              
          <Board players={game.players} currentPlayerId={game.current_player_id} />                                                                                                    
                                                                                                                                                                                       
          <div                                                                                                                                                                         
            style={{                                                                                                                                                                   
              position: "absolute",                                                                                                                                                    
              top: 260,                                                                                                                                                                
              left: 260,                                                                                                                                                               
              background: "rgba(255,255,255,0.92)",                                                                                                                                    
              padding: "12px 18px",                                                                                                                                                    
              borderRadius: 8,                                                                                                                                                         
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)",                                                                                                                                 
              zIndex: 5,                                                                                                                                                               
            }}                                                                                                                                                                         
          >                                                                                                                                                                            
            <h1 style={{ margin: 0, fontSize: "1.5rem" }}>Game {gameId}</h1>                                                                                                           
            <button                                                                                                                                                                    
              onClick={nextTurn}                                                                                                                                                       
              disabled={isSubmitting}                                                                                                                                                  
              style={{                                                                                                                                                                 
                marginTop: "0.6rem",                                                                                                                                                   
                padding: "0.5rem 1rem",                                                                                                                                                
                background: isSubmitting ? "#ccc" : "#1982c4",                                                                                                                         
                color: "#fff",                                                                                                                                                         
                border: "none",                                                                                                                                                        
                borderRadius: "6px",                                                                                                                                                   
                cursor: isSubmitting ? "not-allowed" : "pointer",                                                                                                                      
                fontSize: "1rem",                                                                                                                                                      
              }}                                                                                                                                                                       
            >
              {isSubmitting ? "Processing..." : "Next Turn"}
            </button>
            {lastDiceRoll && (
              <div style={{ marginTop: "0.8rem", fontSize: "0.95rem", color: "#333" }}>
                <div style={{ fontWeight: "bold", marginBottom: "0.3rem" }}>Last Roll:</div>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
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
          </div>

          {/* Ledger positioned on board */}
          <div style={{
            position: "absolute",
            top: 260,
            right: 40,
            width: 420,
            background: "rgba(255,255,255,0.95)",
            padding: "12px 16px",
            borderRadius: 8,
            boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
            zIndex: 5,
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
                {ledger.slice(0, 12).map((txn) => (
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
          <h2>Players</h2>
          <ul style={{ paddingLeft: "1rem" }}>
            {game.players?.map((p) => {
              const idx = p.current_space_id ?? 0;
              const spaceLabel = SPACE_LABELS[idx];
              const cash = playerBalances[String(p.game_player_id)] ?? "?";
              const assets = allPlayerAssets[p.game_player_id] || allPlayerAssets[String(p.game_player_id)] || [];
              const retained = playerRetainedCards[p.game_player_id] || [];
              const isCurrent = p.game_player_id === game.current_player_id;

              // Calculate next player based on turn_order
              const currentPlayer = game.players.find(pl => pl.game_player_id === game.current_player_id);
              const nextTurnOrder = currentPlayer ? ((currentPlayer.turn_order % game.players.length) + 1) : 1;
              const isNext = p.turn_order === nextTurnOrder && !isCurrent;
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
                  <div>
                    {spaceLabel}
                    {" – "}
                    <span style={{ color: "#1982c4" }}>
                      Cash: <b>${cash}</b>
                    </span>
                    {p.in_jail ? " (In Jail)" : ""}
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
                                                                                                                                                                                       
        </div>                                                                                                                                                                         
      </div>                                                                                                                                                                           
    </div>                                                                                                                                                                             
  );                                                                                                                                                                                   
}                                                                                                                                                                                      
                                                                                                                                                                                       
export default App;       