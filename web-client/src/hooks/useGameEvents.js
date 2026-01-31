import { useEffect, useRef } from 'react';

const API_BASE = (import.meta.env.VITE_API_BASE !== undefined && import.meta.env.VITE_API_BASE !== '')
  ? import.meta.env.VITE_API_BASE
  : window.location.origin;

/**
 * Custom hook to listen to Server-Sent Events for real-time game updates.
 *
 * @param {number} gameId - The game ID to listen to
 * @param {string} sessionToken - The authentication token
 * @param {function} onEvent - Callback function (eventType, data) => void
 */
export function useGameEvents(gameId, sessionToken, onEvent) {
  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  useEffect(() => {
    if (!gameId || !sessionToken) {
      return;
    }

    console.log(`[SSE] Connecting to game ${gameId} events...`);

    // Create EventSource connection with token as query parameter
    const url = `${API_BASE}/games/${gameId}/events?token=${encodeURIComponent(sessionToken)}`;

    const eventSource = new EventSource(url, {
      withCredentials: false
    });

    // Store reference
    eventSourceRef.current = eventSource;

    // Event: connected
    eventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Connected:', data);
    });

    // Event: heartbeat
    eventSource.addEventListener('heartbeat', (e) => {
      // Silent heartbeat, just keep connection alive
    });

    // Event: player_joined
    eventSource.addEventListener('player_joined', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Player joined:', data);
      onEvent('player_joined', data);
    });

    // Event: player_ready
    eventSource.addEventListener('player_ready', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Player ready:', data);
      onEvent('player_ready', data);
    });

    // Event: game_started
    eventSource.addEventListener('game_started', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Game started:', data);
      onEvent('game_started', data);
    });

    // Event: turn_played
    eventSource.addEventListener('turn_played', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Turn played:', data);
      onEvent('turn_played', data);
    });

    // Event: purchase_decision
    eventSource.addEventListener('purchase_decision', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Purchase decision:', data);
      onEvent('purchase_decision', data);
    });

    // Event: auction_started
    eventSource.addEventListener('auction_started', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Auction started:', data);
      onEvent('auction_started', data);
    });

    // Event: auction_bid
    eventSource.addEventListener('auction_bid', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Auction bid:', data);
      onEvent('auction_bid', data);
    });

    // Event: auction_pass
    eventSource.addEventListener('auction_pass', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Auction pass:', data);
      onEvent('auction_pass', data);
    });

    // Event: auction_resolved
    eventSource.addEventListener('auction_resolved', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Auction resolved:', data);
      onEvent('auction_resolved', data);
    });

    // Event: game_state_changed
    eventSource.addEventListener('game_state_changed', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Game state changed:', data);
      onEvent('game_state_changed', data);
    });

    // Handle errors
    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);

      // EventSource will automatically try to reconnect
      // We can add custom reconnection logic here if needed
      if (eventSource.readyState === EventSource.CLOSED) {
        console.log('[SSE] Connection closed. Will reconnect...');

        // Clean up
        eventSource.close();

        // Attempt reconnect after delay
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('[SSE] Attempting to reconnect...');
          // The useEffect will run again due to dependencies
        }, 3000);
      }
    };

    // Cleanup function
    return () => {
      console.log('[SSE] Disconnecting from game events...');
      if (eventSource) {
        eventSource.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [gameId, sessionToken, onEvent]);

  return null;
}
