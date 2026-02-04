import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || '';

function PurchaseModal({ gameId, sessionToken, userId, pendingAction, playerBalances, players, onResolved }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const activePlayer = players?.find(p => p.game_player_id === pendingAction.active_player_id);
  const playerBalance = playerBalances[String(pendingAction.active_player_id)] ?? 0;
  const canAfford = playerBalance >= pendingAction.purchase_price;

  // Check if the logged-in user is the active player
  const isActivePlayer = activePlayer?.user_id === userId;

  const handleBuy = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const headers = sessionToken ? {
        'Authorization': `Bearer ${sessionToken}`
      } : {};

      const res = await fetch(`${API_BASE}/games/${gameId}/decisions/buy`, {
        method: "POST",
        headers
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to buy property");
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

      const res = await fetch(`${API_BASE}/games/${gameId}/decisions/pass`, {
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
        minWidth: "400px",
        maxWidth: "500px",
        boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
      }}>
        <h2 style={{ margin: "0 0 16px 0", color: "#1982c4" }}>Purchase Decision</h2>

        <div style={{ marginBottom: "16px" }}>
          <p style={{ fontSize: "1.1rem", margin: "8px 0" }}>
            <strong>{activePlayer?.player_name || "Player"}</strong> landed on:
          </p>
          <p style={{
            fontSize: "1.3rem",
            fontWeight: "bold",
            color: "#333",
            margin: "8px 0",
          }}>
            {pendingAction.property_name}
          </p>
        </div>

        <div style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "20px",
          padding: "12px",
          background: "#f5f5f5",
          borderRadius: "8px",
        }}>
          <div>
            <div style={{ fontSize: "0.85rem", color: "#666" }}>Price</div>
            <div style={{ fontSize: "1.2rem", fontWeight: "bold" }}>${pendingAction.purchase_price}</div>
          </div>
          <div>
            <div style={{ fontSize: "0.85rem", color: "#666" }}>Your Balance</div>
            <div style={{
              fontSize: "1.2rem",
              fontWeight: "bold",
              color: canAfford ? "#2a9d8f" : "#e63946",
            }}>${playerBalance}</div>
          </div>
        </div>

        {!isActivePlayer && (
          <div style={{
            background: "#fff3cd",
            color: "#856404",
            padding: "8px 12px",
            borderRadius: "6px",
            marginBottom: "16px",
            fontSize: "0.9rem",
            fontWeight: "bold",
          }}>
            ⏳ Waiting for {activePlayer?.player_name || "player"} to decide...
          </div>
        )}

        {isActivePlayer && !canAfford && (
          <div style={{
            background: "#ffebee",
            color: "#c62828",
            padding: "8px 12px",
            borderRadius: "6px",
            marginBottom: "16px",
            fontSize: "0.9rem",
          }}>
            Insufficient funds to purchase this property
          </div>
        )}

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
            disabled={isSubmitting || !isActivePlayer}
            style={{
              padding: "10px 24px",
              background: isSubmitting || !isActivePlayer ? "#ccc" : "#6c757d",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              cursor: isSubmitting || !isActivePlayer ? "not-allowed" : "pointer",
              fontSize: "1rem",
            }}
          >
            {isSubmitting ? "..." : "Pass (Auction)"}
          </button>
          <button
            onClick={handleBuy}
            disabled={isSubmitting || !canAfford || !isActivePlayer}
            style={{
              padding: "10px 24px",
              background: isSubmitting || !canAfford || !isActivePlayer ? "#ccc" : "#1982c4",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              cursor: isSubmitting || !canAfford || !isActivePlayer ? "not-allowed" : "pointer",
              fontSize: "1rem",
              fontWeight: "bold",
            }}
          >
            {isSubmitting ? "..." : `Buy for $${pendingAction.purchase_price}`}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PurchaseModal;
