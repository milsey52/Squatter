import { useState } from "react";
import { useTheme } from "../../theme";

const API_BASE = import.meta.env.VITE_API_BASE || '';

/* Chrome + action plumbing shared by every pending-action view: the modal
   frame styles, the submit/error state, and the POST helper that resolves
   the pending. Each view owns one instance. */
export function useModalChrome({ gameId, sessionToken, onResolved }) {
  const { theme } = useTheme();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const headers = {
    'Authorization': `Bearer ${sessionToken}`,
    'Content-Type': 'application/json',
  };
  // Anchored to the centre of the board container (its parent is
  // position:relative), NOT the viewport — so modals sit in the board's open
  // area below the SQUATTER title and never cover the Ledger / Dice panels.
  // Capped to the board height and scrollable in case a tall modal (e.g. the
  // stock-sale declare step) exceeds it.
  const modalStyle = {
    position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
    background: theme.modalBg, color: theme.modalText,
    borderRadius: '12px', padding: '2rem', minWidth: '380px',
    maxWidth: '500px', maxHeight: '88%', overflowY: 'auto',
    boxShadow: `0 10px 40px ${theme.modalShadow}`, zIndex: 50,
  };
  const btnStyle = (bg) => ({
    padding: '0.6rem 1.2rem', background: bg, color: '#fff',
    border: 'none', borderRadius: '6px', cursor: submitting ? 'not-allowed' : 'pointer',
    fontSize: '0.95rem', fontWeight: 'bold', opacity: submitting ? 0.6 : 1,
  });

  const doAction = async (endpoint, body = {}) => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/games/${gameId}/${endpoint}`, {
        method: 'POST', headers, body: JSON.stringify(body)
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload.detail || `Failed: ${res.status}`);
      }
      // Stock Sale buy with insufficient funds: card stays drawn, pending
      // stays open in committed mode — surface the message and refresh so
      // the modal re-renders with the lock state.
      if (payload.status === 'insufficient_funds') {
        setError(
          `Cannot afford ${payload.requested_pens} pens at the locked price ` +
          `(balance $${payload.balance}). Try fewer pens or pass.`
        );
        onResolved();
        return;
      }
      onResolved();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return { modalStyle, btnStyle, submitting, error, setError, doAction };
}
