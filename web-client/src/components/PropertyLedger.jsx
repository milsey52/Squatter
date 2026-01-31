import { useState, useEffect } from 'react';

const API_BASE = (import.meta.env.VITE_API_BASE !== undefined && import.meta.env.VITE_API_BASE !== '')
  ? import.meta.env.VITE_API_BASE
  : window.location.origin;

// Map purchase price to Monopoly color groups
const getPropertyColor = (property) => {
  if (property.space_type === 'transport') return '#000000'; // Black for stations
  if (property.space_type === 'utility') return '#95a5a6'; // Gray for utilities

  const price = property.purchase_price;
  if (price === 600) return '#8B4513'; // Brown
  if (price >= 1000 && price <= 1200) return '#87CEEB'; // Light Blue
  if (price >= 1400 && price <= 1600) return '#FF69B4'; // Pink
  if (price >= 1800 && price <= 2000) return '#FFA500'; // Orange
  if (price >= 2200 && price <= 2400) return '#DC143C'; // Red
  if (price >= 2600 && price <= 2800) return '#FFD700'; // Yellow
  if (price >= 3000 && price <= 3200) return '#228B22'; // Green
  if (price >= 4000 && price <= 5000) return '#0000CD'; // Dark Blue
  return '#cccccc'; // Default gray
};

export default function PropertyLedger({ gameId, sessionToken }) {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check if an owner has a monopoly (owns all properties in a color group)
  const getMonopolies = (props) => {
    const monopolies = new Set();

    // Group properties by color (based on purchase price and type)
    const groups = {};
    props.forEach(prop => {
      const color = getPropertyColor(prop);
      if (!groups[color]) groups[color] = [];
      groups[color].push(prop);
    });

    // Check each group for monopoly
    Object.values(groups).forEach(group => {
      if (group.length < 2) return; // Need at least 2 properties for a group

      const owners = [...new Set(group.map(p => p.owner_name).filter(o => o && o !== 'Bank'))];

      // If all properties in group owned by same player (and not Bank)
      if (owners.length === 1 && group.every(p => p.owner_name === owners[0])) {
        group.forEach(p => monopolies.add(p.asset_id));
      }
    });

    return monopolies;
  };

  useEffect(() => {
    console.log('[PropertyLedger] Mounted with gameId:', gameId, 'sessionToken:', sessionToken ? 'present' : 'missing');

    if (!gameId || !sessionToken) {
      console.log('[PropertyLedger] Missing gameId or sessionToken, not fetching');
      return;
    }

    const fetchProperties = async () => {
      try {
        console.log('[PropertyLedger] Fetching from:', `${API_BASE}/games/${gameId}/properties/all`);
        const response = await fetch(`${API_BASE}/games/${gameId}/properties/all`, {
          headers: {
            'Authorization': `Bearer ${sessionToken}`
          }
        });

        console.log('[PropertyLedger] Response status:', response.status, response.statusText);

        if (!response.ok) {
          throw new Error('Failed to fetch properties');
        }

        const data = await response.json();
        console.log('[PropertyLedger] Fetched properties:', data.properties?.length || 0);
        setProperties(data.properties || []);
        setError(null);
      } catch (error) {
        console.error('[PropertyLedger] Error fetching properties:', error);
        setError(error.message);
      } finally {
        setLoading(false);
      }
    };

    fetchProperties();

    // Refresh every 2 seconds to keep ownership updated
    const interval = setInterval(fetchProperties, 2000);
    return () => clearInterval(interval);
  }, [gameId, sessionToken]);

  if (loading) {
    return (
      <div style={{
        padding: '1rem',
        background: '#f5f5f5',
        borderRadius: '8px',
        textAlign: 'center'
      }}>
        Loading properties...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        padding: '1rem',
        background: '#ffebee',
        borderRadius: '8px',
        textAlign: 'center',
        color: '#c62828'
      }}>
        Error: {error}
      </div>
    );
  }

  return (
    <div style={{
      background: 'rgba(255,255,255,0.95)',
      borderRadius: '12px',
      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
      overflow: 'hidden',
      width: '100%'
    }}>
      <div style={{
        background: 'linear-gradient(135deg, #1982c4 0%, #1569a0 100%)',
        padding: '1rem 1.5rem',
        color: '#fff',
        fontSize: '1.3rem',
        fontWeight: 'bold',
        textAlign: 'center'
      }}>
        📋 Property Ledger
      </div>

      <div style={{
        maxHeight: '1100px',
        overflowY: 'auto',
        padding: '0.5rem'
      }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '0.85rem',
          tableLayout: 'fixed'
        }}>
          <colgroup>
            <col style={{ width: '8px' }} />
            <col style={{ width: '52%' }} />
            <col style={{ width: '20%' }} />
            <col style={{ width: '25%' }} />
          </colgroup>
          <thead>
            <tr style={{
              background: '#e3f2fd',
              position: 'sticky',
              top: 0,
              zIndex: 1
            }}>
              <th style={{
                padding: '0.5rem 0',
                width: '8px',
                borderBottom: '2px solid #1982c4'
              }}></th>
              <th style={{
                padding: '0.5rem 0.4rem',
                textAlign: 'left',
                borderBottom: '2px solid #1982c4',
                fontWeight: 'bold',
                color: '#1569a0',
                fontSize: '0.85rem'
              }}>Name</th>
              <th style={{
                padding: '0.5rem 0.4rem',
                textAlign: 'right',
                borderBottom: '2px solid #1982c4',
                fontWeight: 'bold',
                color: '#1569a0',
                fontSize: '0.85rem'
              }}>Value</th>
              <th style={{
                padding: '0.5rem 0.4rem',
                textAlign: 'left',
                borderBottom: '2px solid #1982c4',
                fontWeight: 'bold',
                color: '#1569a0',
                fontSize: '0.85rem'
              }}>Owner</th>
            </tr>
          </thead>
          <tbody>
            {(() => {
              const monopolies = getMonopolies(properties);

              return properties.map((property, index) => {
                const isOwned = property.owner_name && property.owner_name !== 'Bank';
                const hasMonopoly = monopolies.has(property.asset_id);
                const rowColor = index % 2 === 0 ? '#fff' : '#f8f9fa';
                const groupColor = getPropertyColor(property);

                return (
                <tr key={property.asset_id} style={{
                  background: rowColor,
                  borderBottom: '1px solid #e0e0e0'
                }}>
                  <td style={{
                    padding: '0.35rem 0.4rem',
                    width: hasMonopoly ? '12px' : '8px',
                    background: groupColor,
                    borderLeft: hasMonopoly ? `12px solid ${groupColor}` : `8px solid ${groupColor}`,
                    boxShadow: hasMonopoly ? `0 0 8px ${groupColor}` : 'none'
                  }}></td>
                  <td style={{
                    padding: '0.35rem 0.4rem',
                    color: '#333',
                    fontWeight: isOwned ? 'bold' : 'normal',
                    fontSize: '0.85rem',
                    whiteSpace: 'normal',
                    wordBreak: 'break-word'
                  }}>
                    {property.name}
                  </td>
                  <td style={{
                    padding: '0.35rem 0.4rem',
                    textAlign: 'right',
                    color: '#1982c4',
                    fontWeight: '500',
                    fontSize: '0.85rem',
                    whiteSpace: 'nowrap'
                  }}>
                    ${property.purchase_price.toLocaleString()}
                  </td>
                  <td style={{
                    padding: '0.35rem 0.4rem',
                    color: isOwned ? '#2e7d32' : '#999',
                    fontWeight: isOwned ? 'bold' : 'normal',
                    fontStyle: isOwned ? 'normal' : 'italic',
                    fontSize: '0.85rem',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}>
                    {property.owner_name || 'Bank'}
                    {hasMonopoly && <span style={{ color: '#0000CD', fontSize: '1.1rem', fontWeight: 'bold' }}> ★</span>}
                  </td>
                </tr>);
              });
            })()}
          </tbody>
        </table>

        {properties.length === 0 && (
          <div style={{
            padding: '2rem',
            textAlign: 'center',
            color: '#999',
            fontStyle: 'italic'
          }}>
            No properties found
          </div>
        )}
      </div>
    </div>
  );
}
