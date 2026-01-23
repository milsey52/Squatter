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
      await fetchGameLedgerJackpot();                                                                                                                                                  
    } catch (err) {                                                                                                                                                                    
      setError(err.message);                                                                                                                                                           
    } finally {                                                                                                                                                                        
      setIsSubmitting(false);                                                                                                                                                          
    }                                                                                                                                                                                  
  };                                                                                                                                                                                   
                                                                                                                                                                                       
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
        <div>
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
          </div>                                                                                                                                                                       
        </div>


        {/* Card display section - below board */}
        <div style={{
          width: 1100,
          display: 'flex',
          gap: '2rem',
          marginTop: '1.5rem',
          justifyContent: 'center'
        }}>
          {/* Welfare Centre Card */}
          <div style={{
            background: 'linear-gradient(135deg, #fff 0%, #f8f9fa 100%)',
            border: '2px solid #dee2e6',
            borderRadius: '12px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            padding: '20px',
            minHeight: '200px',
            width: '500px',
          }}>
            <h3 style={{ margin: 0, fontSize: '1.3rem', color: '#6a4c93' }}>
              Welfare Centre
            </h3>
            {lastDrawnCards.WELFARE ? (
              <>
                <h4 style={{
                    fontSize: '1.1rem',
                    fontWeight: 'bold',
                    color: '#1982c4',
                    marginTop: '0.8rem',
                    marginBottom: '0.5rem',
                }}>
                    {lastDrawnCards.WELFARE.title}
                </h4>
                <p style={{
                    fontSize: '0.95rem',
                    lineHeight: '1.5',
                    color: '#333',
                    margin: 0,
                }}>
                    {lastDrawnCards.WELFARE.body_text}
                </p>
              </>
            ) : (
              <p style={{ fontStyle: 'italic', color: '#999', marginTop: '1rem' }}>
                No cards drawn yet
              </p>
            )}
          </div>

          {/* Chance Card */}
          <div style={{
            background: 'linear-gradient(135deg, #fff 0%, #f8f9fa 100%)',
            border: '2px solid #dee2e6',
            borderRadius: '12px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            padding: '20px',
            minHeight: '200px',
            width: '500px',
          }}>
            <h3 style={{ margin: 0, fontSize: '1.3rem', color: '#ff924c' }}>
              Chance
            </h3>
            {lastDrawnCards.CHANCE ? (
              <>
                <h4 style={{
                    fontSize: '1.1rem',
                    fontWeight: 'bold',
                    color: '#1982c4',
                    marginTop: '0.8rem',
                    marginBottom: '0.5rem',
                }}>
                    {lastDrawnCards.CHANCE.title}
                </h4>
                <p style={{
                    fontSize: '0.95rem',
                    lineHeight: '1.5',
                    color: '#333',
                    margin: 0,
                }}>
                    {lastDrawnCards.CHANCE.body_text}
                </p>
              </>
            ) : (
              <p style={{ fontStyle: 'italic', color: '#999', marginTop: '1rem' }}>
                No cards drawn yet
              </p>
            )}
          </div>
        </div>
        </div>

                                                                                                                                                                                       
        {/* Right column: player list + jackpot + ledger */}                                                                                                                           
        <div                                                                                                                                                                           
          style={{                                                                                                                                                                     
            flex: 1,                                                                                                                                                                   
            minWidth: 360,                                                                                                                                                             
            marginTop: "1rem",                                                                                                                                                         
            paddingLeft: "120px",                                                                                                                                                      
            position: "sticky",                                                                                                                                                        
            top: 20,                                                                                                                                                                   
          }}                                                                                                                                                                           
        >                                                                                                                                                                              
          <h2>Ledger (latest)</h2>                                                                                                                                                     
          <table style={{ width: "100%", borderCollapse: "collapse" }}>                                                                                                                
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

          <h2 style={{ marginTop: "2rem" }}>Players</h2>                                                                                                                                                             
          {jackpot !== null && (                                                                                                                                                       
            <div                                                                                                                                                                       
              style={{                                                                                                                                                                 
                fontWeight: "bold",                                                                                                                                                    
                fontSize: "1.2em",                                                                                                                                                     
                color: "#b28500",                                                                                                                                                      
                marginBottom: 12,                                                                                                                                                      
              }}                                                                                                                                                                       
            >                                                                                                                                                                          
              💰 Jackpot: ${jackpot}                                                                                                                                                   
            </div>                                                                                                                                                                     
          )}                                                                                                                                                                           
          <ul style={{ paddingLeft: "1rem" }}>                                                                                                                                         
            {game.players?.map((p) => {                                                                                                                                                
              const idx = p.current_space_id ?? 0;                                                                                                                                     
              const spaceLabel = SPACE_LABELS[idx];                                                                                                                                    
              const cash = playerBalances[String(p.game_player_id)] ?? "?";                                                                                                            
              const assets = allPlayerAssets[p.game_player_id] || allPlayerAssets[String(p.game_player_id)] || [];                                                                     
              const retained = playerRetainedCards[p.game_player_id] || [];                                                                                                            
              return (                                                                                                                                                                 
                <li key={p.game_player_id} style={{ marginBottom: 10 }}>                                                                                                               
                  <strong>{p.player_name}</strong>                                                                                                                                     
                  {" – "}                                                                                                                                                              
                  {spaceLabel}                                                                                                                                                         
                  {" – "}                                                                                                                                                              
                  <span style={{ color: "#1982c4" }}>                                                                                                                                  
                    Cash: <b>${cash}</b>                                                                                                                                               
                  </span>                                                                                                                                                              
                  {p.in_jail ? " (In Jail)" : ""}                                                                                                                                      
                  <br />                                                                                                                                                               
                  <span style={{ fontSize: "0.95em", color: "#222" }}>                                                                                                                 
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
                  </span>                                                                                                                                                              
                  {retained.length > 0 && (                                                                                                                                            
                    <>                                                                                                                                                                 
                      <br />                                                                                                                                                           
                      <span style={{ fontSize: "0.9em", color: "#6a4c93" }}>                                                                                                           
                        🃏 Cards: {retained.map((card, i) => (                                                                                                                         
                          <span key={i} style={{ marginRight: 4 }}>                                                                                                                    
                            {card.name || card.title || card.description}                                                                                                              
                            {i < retained.length - 1 ? ", " : ""}                                                                                                                      
                          </span>                                                                                                                                                      
                        ))}                                                                                                                                                            
                      </span>                                                                                                                                                          
                    </>                                                                                                                                                                
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