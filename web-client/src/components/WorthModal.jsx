import { useState, useEffect } from 'react';
import { Z_INDEX } from '../constants/zIndex';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function WorthModal({ gameId, sessionToken, onClose }) {
  const [worthData, setWorthData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchWorth = async () => {
      try {
        const response = await fetch(`${API_BASE}/games/${gameId}/players/worth`, {
          headers: {
            'Authorization': `Bearer ${sessionToken}`
          }
        });

        if (!response.ok) {
          throw new Error('Failed to fetch worth data');
        }

        const data = await response.json();
        setWorthData(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchWorth();
  }, [gameId, sessionToken]);

  if (loading) {
    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: Z_INDEX.MODAL
      }}>
        <div style={{
          background: 'white',
          padding: '2rem',
          borderRadius: '12px',
          textAlign: 'center'
        }}>
          Loading worth data...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: Z_INDEX.MODAL
      }} onClick={onClose}>
        <div style={{
          background: 'white',
          padding: '2rem',
          borderRadius: '12px',
          textAlign: 'center'
        }} onClick={e => e.stopPropagation()}>
          <p style={{ color: '#d32f2f' }}>{error}</p>
          <button onClick={onClose} style={{
            marginTop: '1rem',
            padding: '0.5rem 1rem',
            background: '#666',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer'
          }}>
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: Z_INDEX.MODAL,
      overflow: 'auto',
      padding: '2rem'
    }} onClick={onClose}>
      <div style={{
        background: 'white',
        borderRadius: '16px',
        maxWidth: '800px',
        width: '100%',
        maxHeight: '90vh',
        overflow: 'auto',
        boxShadow: '0 10px 40px rgba(0,0,0,0.3)'
      }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          padding: '1.5rem',
          borderRadius: '16px 16px 0 0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h2 style={{ margin: 0, fontSize: '1.8rem' }}>💰 Net Worth</h2>
          <button onClick={onClose} style={{
            background: 'rgba(255,255,255,0.2)',
            border: 'none',
            color: 'white',
            fontSize: '1.5rem',
            cursor: 'pointer',
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            ×
          </button>
        </div>

        <div style={{ padding: '2rem' }}>
          {/* Summary Cards */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem',
            marginBottom: '2rem'
          }}>
            <div style={{
              background: '#e8f5e9',
              padding: '1.5rem',
              borderRadius: '12px',
              border: '2px solid #4caf50'
            }}>
              <div style={{ fontSize: '0.9rem', color: '#2e7d32', marginBottom: '0.5rem' }}>
                Total Worth
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#1b5e20' }}>
                ${worthData.total_worth}
              </div>
            </div>

            <div style={{
              background: '#fff3e0',
              padding: '1.5rem',
              borderRadius: '12px',
              border: '2px solid #ff9800'
            }}>
              <div style={{ fontSize: '0.9rem', color: '#e65100', marginBottom: '0.5rem' }}>
                If All Mortgaged
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#bf360c' }}>
                ${worthData.worth_after_mortgage}
              </div>
            </div>
          </div>

          {/* Breakdown */}
          <div style={{
            background: '#f5f5f5',
            borderRadius: '12px',
            padding: '1.5rem',
            marginBottom: '2rem'
          }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.2rem' }}>Breakdown:</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '0.75rem',
                background: 'white',
                borderRadius: '8px'
              }}>
                <span style={{ fontWeight: '500' }}>💵 Cash</span>
                <span style={{ fontWeight: 'bold', color: '#4caf50' }}>
                  ${worthData.cash_balance}
                </span>
              </div>

              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '0.75rem',
                background: 'white',
                borderRadius: '8px'
              }}>
                <span style={{ fontWeight: '500' }}>🏠 Properties</span>
                <span style={{ fontWeight: 'bold', color: '#2196f3' }}>
                  ${worthData.total_property_value}
                </span>
              </div>

              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '0.75rem',
                background: 'white',
                borderRadius: '8px'
              }}>
                <span style={{ fontWeight: '500' }}>🏗️ Improvements</span>
                <span style={{ fontWeight: 'bold', color: '#9c27b0' }}>
                  ${worthData.total_improvement_value}
                </span>
              </div>

              {worthData.jail_cards > 0 && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '0.75rem',
                  background: 'white',
                  borderRadius: '8px'
                }}>
                  <span style={{ fontWeight: '500' }}>
                    🎫 Get Out of Jail Free ({worthData.jail_cards})
                  </span>
                  <span style={{ fontWeight: 'bold', color: '#ff9800' }}>
                    ${worthData.card_value}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Properties List */}
          {worthData.properties.length > 0 && (
            <div>
              <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.2rem' }}>
                Properties & Assets:
              </h3>
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
                maxHeight: '300px',
                overflow: 'auto'
              }}>
                {worthData.properties.map((prop, idx) => (
                  <div key={idx} style={{
                    background: prop.is_mortgaged ? '#ffebee' : '#e3f2fd',
                    padding: '1rem',
                    borderRadius: '8px',
                    border: `2px solid ${prop.is_mortgaged ? '#ef5350' : '#42a5f5'}`
                  }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      marginBottom: '0.5rem'
                    }}>
                      <span style={{ fontWeight: 'bold' }}>{prop.name}</span>
                      <span style={{ fontWeight: 'bold', color: prop.is_mortgaged ? '#c62828' : '#1565c0' }}>
                        ${prop.current_value}
                      </span>
                    </div>
                    <div style={{
                      fontSize: '0.85rem',
                      color: '#666',
                      display: 'flex',
                      gap: '1rem',
                      flexWrap: 'wrap'
                    }}>
                      <span>Purchase: ${prop.purchase_price}</span>
                      <span>Mortgage: ${prop.mortgage_value}</span>
                      {prop.has_hotel && <span style={{ color: '#d32f2f', fontWeight: 'bold' }}>🏨 Hotel</span>}
                      {!prop.has_hotel && prop.improvement_level > 0 && (
                        <span style={{ color: '#388e3c', fontWeight: 'bold' }}>
                          🏠 {prop.improvement_level} house{prop.improvement_level > 1 ? 's' : ''}
                        </span>
                      )}
                      {prop.improvement_value > 0 && (
                        <span>Improvements: ${prop.improvement_value}</span>
                      )}
                      {prop.is_mortgaged && (
                        <span style={{ color: '#c62828', fontWeight: 'bold' }}>MORTGAGED</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {worthData.properties.length === 0 && (
            <div style={{
              textAlign: 'center',
              padding: '2rem',
              color: '#999',
              fontStyle: 'italic'
            }}>
              No properties owned yet
            </div>
          )}

          {/* Close Button */}
          <div style={{
            marginTop: '2rem',
            textAlign: 'center'
          }}>
            <button onClick={onClose} style={{
              padding: '0.75rem 2rem',
              background: '#666',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '1rem',
              fontWeight: 'bold',
              cursor: 'pointer'
            }}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
