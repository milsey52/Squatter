import { useState, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || '';

function AuctionModal({ gameId, sessionToken, userId, pendingAction, playerBalances, players, onResolved }) {
  const [bidAmount, setBidAmount] = useState(pendingAction.min_bid || pendingAction.starting_bid || 1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Update bid amount when min_bid changes (after other players bid)
  useEffect(() => {
    const newMinBid = pendingAction.min_bid || pendingAction.starting_bid || 1;
    setBidAmount(newMinBid);
  }, [pendingAction.min_bid, pendingAction.starting_bid]);

  const currentBidder = players?.find(p => p.game_player_id === pendingAction.next_bidder_id);
  const bidderBalance = playerBalances[String(pendingAction.next_bidder_id)] ?? 0;
  const activeBidderPlayers = players?.filter(p =>
    pendingAction.active_bidders?.includes(p.game_player_id)
  ) || [];

  const highBidder = players?.find(p => p.game_player_id === pendingAction.current_bidder_id);

  // Check if the logged-in user is the current bidder
  const isCurrentBidder = currentBidder?.user_id === userId;

  const handleBid = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const headers = {
        "Content-Type": "application/json"
      };
      if (sessionToken) {
        headers['Authorization'] = `Bearer ${sessionToken}`;
      }

      const res = await fetch(`${API_BASE}/games/${gameId}/auctions/bid`, {
        method: "POST",
        headers,
        body: JSON.stringify({ amount: bidAmount }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to place bid");
      }
      onResolved();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePass = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const headers = sessionToken ? {
        'Authorization': `Bearer ${sessionToken}`
      } : {};

      const res = await fetch(`${API_BASE}/games/${gameId}/auctions/pass`, {
        method: "POST",
        headers
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to pass");
      }
      onResolved();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const canAffordMinBid = bidderBalance >= (pendingAction.min_bid || 1);
  const canAffordCurrentBid = bidderBalance >= bidAmount;

  return (
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: "rgba(0,0,0,0.5)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1000,
    }}>
      <div style={{
        background: "#fff",
        borderRadius: "12px",
        padding: "24px 32px",
        minWidth: "450px",
        maxWidth: "550px",
        boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
      }}>
        <h2 style={{ margin: "0 0 16px 0", color: "#ff924c" }}>Auction</h2>

        <div style={{ marginBottom: "16px" }}>
          <p style={{
            fontSize: "1.3rem",
            fontWeight: "bold",
            color: "#333",
            margin: "8px 0",
          }}>
            {pendingAction.property_name}
          </p>
          <p style={{ fontSize: "0.9rem", color: "#666" }}>
            (List price: ${pendingAction.purchase_price})
          </p>
        </div>

        {/* Current bid info */}
        <div style={{
          background: "#f8f9fa",
          padding: "12px 16px",
          borderRadius: "8px",
          marginBottom: "16px",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
            <span style={{ color: "#666" }}>Starting Bid (25%):</span>
            <span style={{ fontWeight: "bold", color: "#666" }}>
              ${pendingAction.starting_bid || Math.floor(pendingAction.purchase_price * 0.25)}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
            <span style={{ color: "#666" }}>Current Bid:</span>
            <span style={{ fontWeight: "bold", fontSize: "1.2rem", color: "#1982c4" }}>
              ${pendingAction.current_bid || 0}
            </span>
          </div>
          {highBidder && (
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#666" }}>High Bidder:</span>
              <span style={{ fontWeight: "bold" }}>{highBidder.player_name}</span>
            </div>
          )}
        </div>

        {/* Current bidder's turn */}
        <div style={{
          background: isCurrentBidder ? "#e3f2fd" : "#fff3cd",
          border: isCurrentBidder ? "2px solid #1982c4" : "2px solid #ffc107",
          padding: "12px 16px",
          borderRadius: "8px",
          marginBottom: "16px",
        }}>
          <div style={{ fontWeight: "bold", marginBottom: "8px" }}>
            {isCurrentBidder ? "⭐ Your Turn to Bid" : `⏳ Waiting for ${currentBidder?.player_name || "Unknown"} to bid...`}
          </div>
          <div style={{ fontSize: "0.9rem", color: "#666" }}>
            Balance: ${bidderBalance} | Min bid: ${pendingAction.min_bid || 1}
          </div>
        </div>

        {/* Bid input */}
        <div style={{ marginBottom: "16px" }}>
          <label style={{ display: "block", marginBottom: "8px", fontWeight: "bold" }}>
            Your Bid:
          </label>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span style={{ fontSize: "1.2rem" }}>$</span>
            <input
              type="number"
              value={bidAmount}
              onChange={(e) => setBidAmount(Math.max(pendingAction.min_bid || 1, parseInt(e.target.value) || 0))}
              min={pendingAction.min_bid || 1}
              max={bidderBalance}
              disabled={!isCurrentBidder}
              style={{
                flex: 1,
                padding: "10px",
                fontSize: "1.1rem",
                border: "2px solid #ddd",
                borderRadius: "6px",
                background: !isCurrentBidder ? "#f5f5f5" : "#fff",
                cursor: !isCurrentBidder ? "not-allowed" : "text",
              }}
            />
          </div>
          {isCurrentBidder && !canAffordCurrentBid && (
            <div style={{ color: "#e63946", fontSize: "0.85rem", marginTop: "4px" }}>
              Bid exceeds your balance
            </div>
          )}
        </div>

        {/* Remaining bidders */}
        <div style={{ marginBottom: "16px" }}>
          <div style={{ fontSize: "0.85rem", color: "#666", marginBottom: "4px" }}>
            Players still in auction ({activeBidderPlayers.length}):
          </div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {activeBidderPlayers.map(p => (
              <span
                key={p.game_player_id}
                style={{
                  padding: "4px 10px",
                  background: p.game_player_id === pendingAction.next_bidder_id ? "#1982c4" : "#e9ecef",
                  color: p.game_player_id === pendingAction.next_bidder_id ? "#fff" : "#333",
                  borderRadius: "16px",
                  fontSize: "0.85rem",
                }}
              >
                {p.player_name}
              </span>
            ))}
          </div>
        </div>

        {error && (
          <div style={{
            background: "#ffebee",
            color: "#c62828",
            padding: "8px 12px",
            borderRadius: "6px",
            marginBottom: "16px",
            fontSize: "0.9rem",
          }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
          <button
            onClick={handlePass}
            disabled={isSubmitting || !isCurrentBidder}
            style={{
              padding: "10px 24px",
              background: isSubmitting || !isCurrentBidder ? "#ccc" : "#6c757d",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              cursor: isSubmitting || !isCurrentBidder ? "not-allowed" : "pointer",
              fontSize: "1rem",
            }}
          >
            {isSubmitting ? "..." : "Pass"}
          </button>
          <button
            onClick={handleBid}
            disabled={isSubmitting || !canAffordMinBid || !canAffordCurrentBid || !isCurrentBidder}
            style={{
              padding: "10px 24px",
              background: isSubmitting || !canAffordMinBid || !canAffordCurrentBid || !isCurrentBidder ? "#ccc" : "#ff924c",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              cursor: isSubmitting || !canAffordMinBid || !canAffordCurrentBid || !isCurrentBidder ? "not-allowed" : "pointer",
              fontSize: "1rem",
              fontWeight: "bold",
            }}
          >
            {isSubmitting ? "..." : `Bid $${bidAmount}`}
          </button>
        </div>
      </div>
    </div>
  );
}

export default AuctionModal;
