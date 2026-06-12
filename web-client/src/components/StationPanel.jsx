import { useState, useEffect, useRef } from "react";
import { useTheme } from "../theme";

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function StationPanel({ gameId, sessionToken, onClose, onUpdate, isMyTurn = false, inDrought = false }) {
  const { theme } = useTheme();
  const [station, setStation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionMsg, setActionMsg] = useState(null);

  // Draggable window. pos === null → centred (default); once dragged it holds
  // an explicit viewport position so the player can move the panel off the
  // Ledger / Dice / Stud Rams panels behind it.
  const panelRef = useRef(null);
  const [pos, setPos] = useState(null);
  const [drag, setDrag] = useState(null); // {dx, dy}: pointer offset within panel

  useEffect(() => {
    if (!drag) return;
    const onMove = (e) => {
      // Keep a margin so the panel can't be lost off-screen.
      const x = Math.min(Math.max(e.clientX - drag.dx, 0), window.innerWidth - 120);
      const y = Math.min(Math.max(e.clientY - drag.dy, 0), window.innerHeight - 60);
      setPos({ left: x, top: y });
    };
    const onUp = () => setDrag(null);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [drag]);

  const startDrag = (e) => {
    const rect = panelRef.current?.getBoundingClientRect();
    if (!rect) return;
    // Lock the current rendered position, then track the pointer from there
    // (no jump on the first drag, which starts from the centred position).
    setPos({ left: rect.left, top: rect.top });
    setDrag({ dx: e.clientX - rect.left, dy: e.clientY - rect.top });
  };

  const panelStyle = {
    position: 'fixed',
    ...(pos
      ? { left: pos.left, top: pos.top, transform: 'none' }
      : { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }),
    background: theme.modalBg, color: theme.modalText,
    borderRadius: '12px', padding: '1.5rem', width: '700px',
    maxHeight: '80vh', overflowY: 'auto',
    boxShadow: `0 10px 40px ${theme.modalShadow}`, zIndex: 8000,
  };

  const headers = {
    'Authorization': `Bearer ${sessionToken}`,
    'Content-Type': 'application/json'
  };

  const fetchStation = async () => {
    try {
      const res = await fetch(`${API_BASE}/games/${gameId}/station`, { headers });
      if (!res.ok) throw new Error('Failed to load station');
      const data = await res.json();
      setStation(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStation(); }, [gameId]);

  const doAction = async (endpoint, body = {}) => {
    setActionMsg(null);
    try {
      const res = await fetch(`${API_BASE}/games/${gameId}/station/${endpoint}`, {
        method: 'POST', headers, body: JSON.stringify(body)
      });
      // Read body as text first so a non-JSON error page (e.g. 500 HTML) doesn't
      // crash the JSON parser before we can surface a useful message.
      const raw = await res.text();
      let data = null;
      try { data = raw ? JSON.parse(raw) : null; } catch { data = null; }
      if (!res.ok) {
        const detail = (data && data.detail) || raw || `HTTP ${res.status}`;
        throw new Error(detail);
      }
      setActionMsg({ text: (data && data.status) || 'Success', error: false });
      fetchStation();
      onUpdate();
    } catch (e) {
      setActionMsg({ text: e.message, error: true });
      // Always re-sync paddock state on failure — UI may be stale.
      fetchStation();
    }
  };

  const paddockTypeColor = { natural: '#8d6e63', improved: '#66bb6a', irrigated: '#42a5f5' };

  if (loading) return <div style={panelStyle}><p>Loading...</p></div>;
  if (error) return <div style={panelStyle}><p style={{ color: 'red' }}>{error}</p><button onClick={onClose}>Close</button></div>;
  if (!station) return null;

  return (
    <div ref={panelRef} style={panelStyle}>
      <div
        onMouseDown={startDrag}
        title="Drag to move"
        style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: '1rem', cursor: 'move', userSelect: 'none',
        }}
      >
        <h2 style={{ margin: 0, color: '#2d5016' }}>⠿ My Station</h2>
        <button onClick={onClose} onMouseDown={(e) => e.stopPropagation()}
          style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer' }}>X</button>
      </div>

      {/* Summary */}
      <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <div><strong>Balance:</strong> ${station.balance}</div>
        <div><strong>Total Sheep:</strong> {station.total_sheep?.toLocaleString()} ({station.total_pens} pens)</div>
        <div><strong>Empty Pens:</strong> {station.empty_pens}</div>
      </div>

      {/* Paddocks */}
      <h3 style={{ margin: '0.5rem 0' }}>Paddocks</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.8rem' }}>
        {station.paddocks?.map(pad => (
          <div key={pad.paddock_id} style={{
            border: `2px solid ${paddockTypeColor[pad.paddock_type]}`,
            borderRadius: '8px', padding: '10px', background: '#fafafa'
          }}>
            <div style={{ fontWeight: 'bold', color: paddockTypeColor[pad.paddock_type], textTransform: 'capitalize' }}>
              #{pad.paddock_number} - {pad.paddock_type}
            </div>
            <div style={{ fontSize: '0.85rem', marginTop: 4 }}>
              {pad.sheep_pens}/{pad.max_pens} pens
              {pad.is_mortgaged && <span style={{ color: '#d32f2f', marginLeft: 6 }}>(Mortgaged)</span>}
            </div>
            <div style={{ display: 'flex', gap: '4px', marginTop: '6px', flexWrap: 'wrap' }}>
              {pad.paddock_type === 'natural' && !pad.is_mortgaged && (() => {
                const blocked = !isMyTurn || inDrought;
                const reason = !isMyTurn ? "Only allowed on your turn"
                  : inDrought ? "Cannot upgrade paddocks while in drought" : undefined;
                return (
                  <button onClick={() => doAction('upgrade-paddock', { paddock_id: pad.paddock_id, target_type: 'improved' })}
                    disabled={blocked}
                    title={reason}
                    style={{ ...smallBtn('#66bb6a'), opacity: blocked ? 0.45 : 1, cursor: blocked ? 'not-allowed' : 'pointer' }}>Improve ($500)</button>
                );
              })()}
              {pad.paddock_type === 'improved' && !pad.is_mortgaged && (() => {
                const blocked = !isMyTurn || inDrought;
                const reason = !isMyTurn ? "Only allowed on your turn"
                  : inDrought ? "Cannot upgrade paddocks while in drought" : undefined;
                return (
                  <button onClick={() => doAction('upgrade-paddock', { paddock_id: pad.paddock_id, target_type: 'irrigated' })}
                    disabled={blocked}
                    title={reason}
                    style={{ ...smallBtn('#42a5f5'), opacity: blocked ? 0.45 : 1, cursor: blocked ? 'not-allowed' : 'pointer' }}>Irrigate ($1500)</button>
                );
              })()}
              {!pad.is_mortgaged && (
                <button onClick={() => doAction('mortgage-paddock', { paddock_id: pad.paddock_id })}
                  style={smallBtn('#d32f2f')}>Mortgage</button>
              )}
              {pad.is_mortgaged && (
                <button onClick={() => doAction('unmortgage-paddock', { paddock_id: pad.paddock_id })}
                  style={smallBtn('#4caf50')}>Unmortgage</button>
              )}
            </div>
            {!pad.is_mortgaged && pad.sheep_pens > 0 && (
              <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px dashed #ccc', fontSize: '0.78rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  Move
                  <input type="number" min={1} max={pad.sheep_pens}
                    defaultValue={1}
                    style={{ width: 36 }}
                    id={`mv-pens-${pad.paddock_id}`} />
                  to
                  <select id={`mv-dest-${pad.paddock_id}`} style={{ flex: 1, minWidth: 60 }}>
                    {(station.paddocks || [])
                      .filter(p2 => p2.paddock_id !== pad.paddock_id && !p2.is_mortgaged
                                    && (p2.max_pens - p2.sheep_pens) > 0)
                      .map(p2 => (
                        <option key={p2.paddock_id} value={p2.paddock_id}>
                          #{p2.paddock_number} {p2.paddock_type[0].toUpperCase()} ({p2.max_pens - p2.sheep_pens} free)
                        </option>
                      ))}
                  </select>
                </label>
                <button
                  onClick={() => {
                    const pensVal = Number(document.getElementById(`mv-pens-${pad.paddock_id}`).value);
                    const destVal = Number(document.getElementById(`mv-dest-${pad.paddock_id}`).value);
                    if (pensVal > 0 && destVal) {
                      doAction('move-sheep', {
                        from_paddock_id: pad.paddock_id,
                        to_paddock_id: destVal,
                        pens: pensVal,
                      });
                    }
                  }}
                  style={{ ...smallBtn('#1982c4'), marginTop: 4, width: '100%' }}>Move</button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <h3 style={{ margin: '1rem 0 0.5rem' }}>Actions</h3>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button onClick={() => doAction('sell-haystack')} style={smallBtn('#a1887f')}>Sell Haystack ($350)</button>
        <button onClick={() => {
          const amt = prompt('How many pens to sell? (Emergency $400/pen)');
          if (amt && Number(amt) > 0) doAction('sell-to-bank', { pens: Number(amt) });
        }} style={smallBtn('#d32f2f')}>Emergency Sell</button>
      </div>

      {/* Stud rams */}
      {station.stud_rams_owned?.length > 0 && (
        <>
          <h3 style={{ margin: '1rem 0 0.5rem' }}>My Stud Rams</h3>
          {station.stud_rams_owned.map(ram => (
            <div key={ram.space_id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: 4 }}>
              <span>{ram.space_name || `Ram at space ${ram.space_id}`}</span>
              <button onClick={() => doAction('sell-stud-ram', { space_id: ram.space_id })}
                style={smallBtn('#ff9800')}>Sell ($400)</button>
            </div>
          ))}
        </>
      )}

      {actionMsg && (
        <p style={{
          marginTop: '0.5rem', fontWeight: 'bold',
          padding: '0.5rem 0.75rem', borderRadius: 6,
          color: actionMsg.error ? '#fff' : '#1b5e20',
          background: actionMsg.error ? '#d32f2f' : '#e8f5e9',
          border: `1px solid ${actionMsg.error ? '#b71c1c' : '#a5d6a7'}`,
        }}>
          {actionMsg.error ? '⚠ ' : ''}{actionMsg.text}
        </p>
      )}
    </div>
  );
}


const smallBtn = (bg) => ({
  padding: '3px 8px', background: bg, color: '#fff', border: 'none',
  borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem'
});
