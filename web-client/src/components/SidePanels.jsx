import { useTheme } from "../theme";

/* Small read-only sidebar panels: winner banner, stud ram register,
   ledger, and the dice-roll register. */

const API_BASE = import.meta.env.VITE_API_BASE || '';

export function WinnerBanner({ pendingAction, winner, gameOver, gameId, sessionToken, zIndex, onReturnToMenu }) {
  // Triggers on either the game_over SSE event OR a game_won pending
  // action, since the backend only creates the latter.
  const gameWonPending = pendingAction?.action_type === 'game_won' ? pendingAction : null;
  const winnerName = winner || gameWonPending?.action_data?.winner_name;
  if (!((gameOver || !!gameWonPending) && winnerName)) return null;

  const returnToMenu = async () => {
    // Resolve the lingering pending action if present so future joiners don't see it.
    if (gameWonPending) {
      try {
        await fetch(`${API_BASE}/games/${gameId}/decisions/acknowledge`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${sessionToken}` },
        });
      } catch (_) {}
    }
    onReturnToMenu();
  };

  return (
    <div style={{
      position: "absolute", top: "50%",