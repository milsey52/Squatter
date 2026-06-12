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
  const [connectionState, setConnectionState] = useState('disconnected');

  // Use a ref for the callback to avoid reconnecting when it changes
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  // Use a counter to force reconnection on errors
  const [reconnectTrigger, setReconnectTrigger] = useState(0);

  useEffect(() => {
    if (!gameId || !sessionToken) {
      return;
    }

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

    console.log(`[SSE] Connecting to game ${gameId} events...`);
    setConnectionState('connecting');

    const url = `${API_BASE}/games/${gameId}/events?token=${encodeURIComponent(sessionToken)}`;

    const eventSource = new EventSource(url, {
      withCredentials: false
    });

    eventSourceRef.current = eventSource;

    // Helper to call the current callback
    const callOnEvent = (eventType, data) => {
      if (onEventRef.current) {
        onEventRef.current(eventType, data);
      }
    };

    // Defensive JSON.parse — if a payload is malformed, log it and return null
    // instead of throwing. Prevents one bad event from flooding the console.
    const safeParse = (raw, eventName) => {
      try {
        return JSON.parse(raw);
      } catch (err) {
        console.warn(`[SSE] Bad JSON for ${eventName}:`, err.message, '— payload:', raw);
        return null;
      }
    };

    // Event: connected
    eventSource.addEventListener('connected', (e) => {
      const data = safeParse(e.data, 'connected');
      if (data === null) return;
      console.log('[SSE] Connected:', data);
      setConnectionState('connected');
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY;
    });

    // Event: heartbeat
    eventSource.addEventListener('heartbeat', () => {
      // Silent heartbeat, just keep connection alive
    });

    // Event: player_joined
    eventSource.addEventListener('player_joined', (e) => {
      const data = safeParse(e.data, 'player_joined');
      if (data === null) return;
      console.log('[SSE] Player joined:', data);
      callOnEvent('player_joined', data);
    });

    // Event: player_ready
    eventSource.addEventListener('player_ready', (e) => {
      const data = safeParse(e.data, 'player_ready');
      if (data === null) return;
      console.log('[SSE] Player ready:', data);
      callOnEvent('player_ready', data);
    });

    // Event: game_started
    eventSource.addEventListener('game_started', (e) => {
      const data = safeParse(e.data, 'game_started');
      if (data === null) return;
      console.log('[SSE] Game started:', data);
      callOnEvent('game_started', data);
    });

    // Event: turn_played
    eventSource.addEventListener('turn_played', (e) => {
      const data = safeParse(e.data, 'turn_played');
      if (data === null) return;
      console.log('[SSE] Turn played:', data);
      callOnEvent('turn_played', data);
    });

    // Event: game_state_changed
    eventSource.addEventListener('game_state_changed', (e) => {
      const data = safeParse(e.data, 'game_state_changed');
      if (data === null) return;
      console.log('[SSE] Game state changed:', data);
      callOnEvent('game_state_changed', data);
    });

    // Event: ai_thinking — AI "thinking out loud" narration. EventSource
    // dispatches by event name, so a new server event needs its own listener
    // here or it is silently dropped.
    eventSource.addEventListener('ai_thinking', (e) => {
      const data = safeParse(e.data, 'ai_thinking');
      if (data === null) return;
      callOnEvent('ai_thinking', data);
    });

    eventSource.addEventListener('game_over', (e) => {
      const data = safeParse(e.data, 'game_over');
      if (data === null) return;
      console.log('[SSE] Game over:', data);
      callOnEvent('game_over', data);
    });

    // Handle errors and reconnection
    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);
      setConnectionState('disconnected');

      // Close the failed connection
      eventSource.close();
      eventSourceRef.current = null;

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
  }, [gameId, sessionToken, reconnectTrigger]);

  return { connectionState };
}
