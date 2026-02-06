import { useEffect, useRef, useState, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

// Reconnection settings
const INITIAL_RECONNECT_DELAY = 1000;  // 1 second
const MAX_RECONNECT_DELAY = 30000;     // 30 seconds max
const RECONNECT_MULTIPLIER = 1.5;      // Exponential backoff

/**
 * Custom hook to listen to Server-Sent Events for real-time game updates.
 * Includes automatic reconnection with exponential backoff.
 *
 * @param {number} gameId - The game ID to listen to
 * @param {string} sessionToken - The authentication token
 * @param {function} onEvent - Callback function (eventType, data) => void
 */
export function useGameEvents(gameId, sessionToken, onEvent) {
  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY);
  const [connectionState, setConnectionState] = useState('disconnected'); // 'disconnected', 'connecting', 'connected'

  // Use a counter to force reconnection
  const [reconnectTrigger, setReconnectTrigger] = useState(0);

  const connect = useCallback(() => {
    if (!gameId || !sessionToken) {
      return null;
    }

    console.log(`[SSE] Connecting to game ${gameId} events...`);
    setConnectionState('connecting');

    const url = `${API_BASE}/games/${gameId}/events?token=${encodeURIComponent(sessionToken)}`;

    const eventSource = new EventSource(url, {
      withCredentials: false
    });

    // Event: connected
    eventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Connected:', data);
      setConnectionState('connected');
      // Reset reconnect delay on successful connection
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY;
    });

    // Event: heartbeat
    eventSource.addEventListener('heartbeat', (e) => {
      // Silent heartbeat, just keep connection alive
      // But use it to confirm we're still connected
      if (connectionState !== 'connected') {
        setConnectionState('connected');
      }
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

    // Event: trade events
    eventSource.addEventListener('trade_initiated', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Trade initiated:', data);
      onEvent('trade_initiated', data);
    });

    eventSource.addEventListener('trade_status_changed', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Trade status changed:', data);
      onEvent('trade_status_changed', data);
    });

    eventSource.addEventListener('trade_offer_updated', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Trade offer updated:', data);
      onEvent('trade_offer_updated', data);
    });

    eventSource.addEventListener('trade_accepted', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Trade accepted:', data);
      onEvent('trade_accepted', data);
    });

    eventSource.addEventListener('trade_executed', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Trade executed:', data);
      onEvent('trade_executed', data);
    });

    eventSource.addEventListener('trade_cancelled', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Trade cancelled:', data);
      onEvent('trade_cancelled', data);
    });

    // Event: bankruptcy events
    eventSource.addEventListener('player_resigned', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Player resigned:', data);
      onEvent('player_resigned', data);
    });

    eventSource.addEventListener('debt_resolved', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Debt resolved:', data);
      onEvent('debt_resolved', data);
    });

    eventSource.addEventListener('game_over', (e) => {
      const data = JSON.parse(e.data);
      console.log('[SSE] Game over:', data);
      onEvent('game_over', data);
    });

    // Handle errors and reconnection
    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);
      setConnectionState('disconnected');

      // Close the failed connection
      eventSource.close();

      // Calculate next reconnect delay with exponential backoff
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(
        delay * RECONNECT_MULTIPLIER,
        MAX_RECONNECT_DELAY
      );

      console.log(`[SSE] Will attempt reconnect in ${delay}ms...`);

      // Schedule reconnection
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('[SSE] Attempting to reconnect...');
        setReconnectTrigger(prev => prev + 1);
      }, delay);
    };

    return eventSource;
  }, [gameId, sessionToken, onEvent, connectionState]);

  useEffect(() => {
    // Clear any pending reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // Create new connection
    const eventSource = connect();
    eventSourceRef.current = eventSource;

    // Cleanup function
    return () => {
      console.log('[SSE] Disconnecting from game events...');
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [gameId, sessionToken, connect, reconnectTrigger]);

  return { connectionState };
}
