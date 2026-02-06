import { useState } from "react";
import { Z_INDEX } from '../constants/zIndex';

const API_BASE = import.meta.env.VITE_API_BASE || '';

function JailModal({ gameId, sessionToken, userId, pendingAction, players, onResolved }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const activePlayer = players?.find(p => p.game_player_id === pendingAction.active_player_id);
  const isActivePlayer = activePlayer?.user_id === userId;
  const hasGetOutCard = pendingAction.has_get_out_card || false;

  const handleAcknowledge = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const headers = sessionToken ? {
        'Authorization': `Bearer ${sessionToken}`
      } : {};

      const res = await fetch(`${API_BASE}/games/${gameId}/decisions/acknowledge-jail`, {
        method: "POST",
        headers
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to acknowledge jail");
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
      zIndex: Z_INDEX.MODAL
    }}>
      <div style={{
        background: "#fff",
        padding: "30px",
        borderRadius: "8px",
        minWidth: "400px",
        maxWidth: "500px",
        boxShadow: "0 4px 6px rgba(0,0,0,0.1)"
      }}>
        <h2 style={{ marginTop: 0, color: "#d32f2f" }}>
          🚔 Police Arrest - Imprisonment!
        </h2>

        <div style={{ marginBottom: "20px" }}>
          <p style={{ fontSize: "16px", marginBottom: "15px" }}>
            <strong>{activePlayer?.player_name || "Player"}</strong> has landed on
            <strong> Police Arrest – Imprisonment</strong> and is being sent to jail!
          </p>

          <p style={{ fontSize: "14px", color: "#666", marginBottom: "10px" }}>
            You will be moved to the <strong>Visit Jail</strong> space and will not collect any money en route.
          </p>

          <div style={{
            background: "#f5f5f5",
            padding: "15px",
            borderRadius: "5px",
            marginTop: "15px"
          }}>
            <p style={{ margin: "0 0 10px 0", fontWeight: "bold" }}>
              Options to get out of jail:
            </p>
            <ul style={{ margin: 0, paddingLeft: "20px" }}>
              <li>Roll doubles on your turn</li>
              {hasGetOutCard && <li style={{ color: "#2e7d32" }}>Use your "Get Out of Jail Free" card</li>}
              {!hasGetOutCard && <li>Obtain a "Get Out of Jail Free" card</li>}
              <li>After 3 turns in jail, automatically pay $500 fine</li>
            </ul>
          </div>
        </div>

        {error && (
          <div style={{
            background: "#ffebee",
            color: "#c62828",
            padding: "10px",
            borderRadius: "4px",
            marginBottom: "15px"
          }}>
            {error}
          </div>
        )}

        {isActivePlayer ? (
          <button
            onClick={handleAcknowledge}
            disabled={isSubmitting}
            style={{
              width: "100%",
              padding: "12px",
              fontSize: "16px",
              fontWeight: "bold",
              background: isSubmitting ? "#ccc" : "#1976d2",
              color: "#fff",
              border: "none",
              borderRadius: "5px",
              cursor: isSubmitting ? "not-allowed" : "pointer"
            }}
          >
            {isSubmitting ? "Processing..." : "Acknowledge & Go to Jail"}
          </button>
        ) : (
          <div style={{
            padding: "12px",
            background: "#fff3cd",
            border: "1px solid #ffc107",
            borderRadius: "5px",
            textAlign: "center",
            color: "#856404"
          }}>
            Waiting for {activePlayer?.player_name} to acknowledge...
          </div>
        )}
      </div>
    </div>
  );
}

export default JailModal;
