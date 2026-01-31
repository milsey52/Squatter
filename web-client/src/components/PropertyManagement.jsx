import { useState, useEffect } from 'react';

const API_BASE = (import.meta.env.VITE_API_BASE !== undefined && import.meta.env.VITE_API_BASE !== '')
  ? import.meta.env.VITE_API_BASE
  : window.location.origin;

export default function PropertyManagement({ gameId, sessionToken, playerBalance, onClose, onUpdate }) {
  const [properties, setProperties] = useState({ groups: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [processing, setProcessing] = useState(null);

  useEffect(() => {
    fetchProperties();
  }, [gameId, sessionToken]);

  const fetchProperties = async () => {
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/properties`, {
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) throw new Error('Failed to load properties');

      const data = await response.json();
      setProperties(data);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const improveProperty = async (assetId, improvementType) => {
    setProcessing(assetId);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/properties/${assetId}/improve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionToken}`
        },
        body: JSON.stringify({ improvement_type: improvementType })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to improve property');
      }

      const result = await response.json();
      const improvementName = improvementType === 'house' ? 'House' : 'Hotel';
      setSuccess(`✓ ${improvementName} purchased successfully! Cost: $${result.cost}`);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);

      await fetchProperties();
      if (onUpdate) onUpdate();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(null);
    }
  };

  const unimproveProperty = async (assetId, improvementType) => {
    setProcessing(assetId);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/properties/${assetId}/unimprove`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionToken}`
        },
        body: JSON.stringify({ improvement_type: improvementType })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to sell improvement');
      }

      const result = await response.json();
      const improvementName = improvementType === 'house' ? 'House' : 'Hotel';
      setSuccess(`✓ ${improvementName} sold successfully! Refund: $${result.refund}`);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);

      await fetchProperties();
      if (onUpdate) onUpdate();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(null);
    }
  };

  const mortgageProperty = async (assetId) => {
    setProcessing(assetId);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/properties/${assetId}/mortgage`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to mortgage property');
      }

      const result = await response.json();
      setSuccess(`✓ Property mortgaged! Received: $${result.mortgage_value}`);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);

      await fetchProperties();
      if (onUpdate) onUpdate();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(null);
    }
  };

  const unmortgageProperty = async (assetId) => {
    setProcessing(assetId);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/properties/${assetId}/unmortgage`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to unmortgage property');
      }

      const result = await response.json();
      setSuccess(`✓ Property unmortgaged! Cost: $${result.cost}`);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);

      await fetchProperties();
      if (onUpdate) onUpdate();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(null);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <div>Loading properties...</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        padding: '1rem 1.5rem',
        background: 'linear-gradient(135deg, #6a4c93 0%, #8b6fb0 100%)',
        borderRadius: '9px 9px 0 0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h2 style={{ margin: 0, color: '#fff', fontSize: '1.3rem' }}>Manage Properties</h2>
        <button
          onClick={onClose}
          style={{
            background: 'transparent',
            border: '2px solid #fff',
            color: '#fff',
            borderRadius: '6px',
            padding: '0.4rem 0.8rem',
            cursor: 'pointer',
            fontSize: '1rem',
            fontWeight: 'bold'
          }}
        >
          ✕
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div style={{
          background: '#ffebee',
          color: '#c62828',
          padding: '0.8rem',
          margin: '1rem',
          borderRadius: '6px',
          fontWeight: 'bold',
          border: '2px solid #c62828'
        }}>
          ❌ {error}
        </div>
      )}

      {/* Success Message */}
      {success && (
        <div style={{
          background: '#e8f5e9',
          color: '#2e7d32',
          padding: '0.8rem',
          margin: '1rem',
          borderRadius: '6px',
          fontWeight: 'bold',
          border: '2px solid #4caf50'
        }}>
          {success}
        </div>
      )}

      {/* Balance Display */}
      <div style={{
        padding: '1rem 1.5rem',
        background: '#f5f5f5',
        borderBottom: '2px solid #ddd',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <span style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>Your Balance:</span>
        <span style={{ fontSize: '1.3rem', color: '#1b5e20', fontWeight: 'bold' }}>${playerBalance}</span>
      </div>

      {/* Content */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '1rem'
      }}>
        {properties.groups.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#666', padding: '2rem' }}>
            You don't own any properties yet.
          </div>
        ) : (
          properties.groups.map((group, groupIdx) => (
            <div key={groupIdx} style={{
              marginBottom: '1.5rem',
              border: '2px solid #ddd',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              {/* Group Header */}
              <div style={{
                background: group.has_monopoly ? '#e8f5e9' : '#f5f5f5',
                padding: '0.8rem 1rem',
                borderBottom: '2px solid #ddd',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <strong>{group.group_name}</strong>
                  {group.has_monopoly && (
                    <span style={{
                      marginLeft: '0.5rem',
                      background: '#4caf50',
                      color: '#fff',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '4px',
                      fontSize: '0.8rem',
                      fontWeight: 'bold'
                    }}>
                      MONOPOLY
                    </span>
                  )}
                  {group.any_mortgaged && (
                    <span style={{
                      marginLeft: '0.5rem',
                      background: '#f44336',
                      color: '#fff',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '4px',
                      fontSize: '0.8rem',
                      fontWeight: 'bold'
                    }}>
                      MORTGAGED
                    </span>
                  )}
                  {group.any_improvements && (
                    <span style={{
                      marginLeft: '0.5rem',
                      background: '#ff9800',
                      color: '#fff',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '4px',
                      fontSize: '0.8rem',
                      fontWeight: 'bold'
                    }} title="Must sell all houses/hotels before mortgaging">
                      HAS IMPROVEMENTS
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.9rem', color: '#666' }}>
                  House: ${group.house_cost} • Hotel: ${group.hotel_cost}
                </div>
              </div>

              {/* Properties in Group */}
              {group.properties.map((property) => {
                const canBuyHouse = property.can_improve &&
                                   !property.has_hotel &&
                                   property.improvement_level < 4 &&
                                   playerBalance >= group.house_cost;

                const canBuyHotel = property.can_improve &&
                                   !property.has_hotel &&
                                   property.improvement_level === 4 &&
                                   playerBalance >= group.hotel_cost;

                const canSellHouse = property.improvement_level > 0 && !property.has_hotel;
                const canSellHotel = property.has_hotel;

                return (
                  <div key={property.asset_id} style={{
                    padding: '1rem',
                    borderBottom: '1px solid #eee',
                    background: property.is_mortgaged ? '#ffebee' : '#fff'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.8rem' }}>
                      <div>
                        <div style={{ fontSize: '1.1rem', fontWeight: 'bold', marginBottom: '0.3rem' }}>
                          {property.name}
                          {property.is_mortgaged && (
                            <span style={{ color: '#d32f2f', fontSize: '0.9rem', marginLeft: '0.5rem' }}>
                              [MORTGAGED]
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: '0.9rem', color: '#666' }}>
                          Current Rent: <strong>${property.current_rent}</strong>
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        {property.has_hotel ? (
                          <div style={{
                            fontSize: '1.5rem',
                            background: '#ff9800',
                            color: '#fff',
                            padding: '0.3rem 0.8rem',
                            borderRadius: '6px',
                            fontWeight: 'bold'
                          }}>
                            🏨 HOTEL
                          </div>
                        ) : property.improvement_level > 0 ? (
                          <div style={{
                            fontSize: '1.2rem',
                            background: '#4caf50',
                            color: '#fff',
                            padding: '0.3rem 0.8rem',
                            borderRadius: '6px',
                            fontWeight: 'bold'
                          }}>
                            🏠 {property.improvement_level} {property.improvement_level === 1 ? 'House' : 'Houses'}
                          </div>
                        ) : null}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    {!property.is_mortgaged && (
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        {/* Buy House */}
                        <button
                          onClick={() => improveProperty(property.asset_id, 'house')}
                          disabled={!canBuyHouse || processing === property.asset_id}
                          style={{
                            padding: '0.5rem 1rem',
                            background: canBuyHouse ? '#4caf50' : '#ccc',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: canBuyHouse ? 'pointer' : 'not-allowed',
                            fontSize: '0.9rem',
                            fontWeight: 'bold'
                          }}
                          title={
                            !group.has_monopoly ? 'Need to own all properties in color group' :
                            group.any_mortgaged ? 'Cannot build - a property in this group is mortgaged' :
                            property.improvement_level >= 4 ? 'Maximum houses (upgrade to hotel)' :
                            playerBalance < group.house_cost ? `Insufficient funds. Need $${group.house_cost}` :
                            ''
                          }
                        >
                          {processing === property.asset_id ? '⏳ Buying...' : `+House ($${group.house_cost})`}
                        </button>

                        {/* Buy Hotel */}
                        {property.improvement_level === 4 && !property.has_hotel && (
                          <button
                            onClick={() => improveProperty(property.asset_id, 'hotel')}
                            disabled={!canBuyHotel || processing === property.asset_id}
                            style={{
                              padding: '0.5rem 1rem',
                              background: canBuyHotel ? '#ff9800' : '#ccc',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: canBuyHotel ? 'pointer' : 'not-allowed',
                              fontSize: '0.9rem',
                              fontWeight: 'bold'
                            }}
                          >
                            {processing === property.asset_id ? '...' : `+Hotel ($${group.hotel_cost})`}
                          </button>
                        )}

                        {/* Sell House */}
                        {canSellHouse && (
                          <button
                            onClick={() => unimproveProperty(property.asset_id, 'house')}
                            disabled={processing === property.asset_id}
                            style={{
                              padding: '0.5rem 1rem',
                              background: '#f44336',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              fontSize: '0.9rem',
                              fontWeight: 'bold'
                            }}
                          >
                            {processing === property.asset_id ? '...' : `Sell House ($${group.house_cost / 2})`}
                          </button>
                        )}

                        {/* Sell Hotel */}
                        {canSellHotel && (
                          <button
                            onClick={() => unimproveProperty(property.asset_id, 'hotel')}
                            disabled={processing === property.asset_id}
                            style={{
                              padding: '0.5rem 1rem',
                              background: '#f44336',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              fontSize: '0.9rem',
                              fontWeight: 'bold'
                            }}
                          >
                            {processing === property.asset_id ? '...' : `Sell Hotel ($${group.hotel_cost / 2})`}
                          </button>
                        )}

                        {/* Mortgage Property */}
                        {property.improvement_level === 0 && !property.has_hotel && (
                          <button
                            onClick={() => mortgageProperty(property.asset_id)}
                            disabled={processing === property.asset_id || group.any_improvements}
                            style={{
                              padding: '0.5rem 1rem',
                              background: group.any_improvements ? '#ccc' : '#9c27b0',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '6px',
                              cursor: group.any_improvements ? 'not-allowed' : 'pointer',
                              fontSize: '0.9rem',
                              fontWeight: 'bold'
                            }}
                            title={
                              group.any_improvements
                                ? 'Cannot mortgage while any property in group has improvements'
                                : `Receive $${property.mortgage_value || 0} from the bank`
                            }
                          >
                            {processing === property.asset_id ? '⏳ Processing...' : `Mortgage ($${property.mortgage_value || 0})`}
                          </button>
                        )}
                      </div>
                    )}

                    {/* Unmortgage button for mortgaged properties */}
                    {property.is_mortgaged && (
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                        <button
                          onClick={() => unmortgageProperty(property.asset_id)}
                          disabled={processing === property.asset_id || playerBalance < Math.floor((property.mortgage_value || 0) * 1.10)}
                          style={{
                            padding: '0.5rem 1rem',
                            background: playerBalance < Math.floor((property.mortgage_value || 0) * 1.10) ? '#ccc' : '#2196f3',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: playerBalance < Math.floor((property.mortgage_value || 0) * 1.10) ? 'not-allowed' : 'pointer',
                            fontSize: '0.9rem',
                            fontWeight: 'bold'
                          }}
                          title={
                            playerBalance < Math.floor((property.mortgage_value || 0) * 1.10)
                              ? `Insufficient funds. Need $${Math.floor((property.mortgage_value || 0) * 1.10)}, have $${playerBalance}`
                              : `Pay $${Math.floor((property.mortgage_value || 0) * 1.10)} (mortgage + 10% interest)`
                          }
                        >
                          {processing === property.asset_id ? '⏳ Processing...' : `Unmortgage ($${Math.floor((property.mortgage_value || 0) * 1.10)})`}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>

      {/* Footer Info */}
      <div style={{
        padding: '1rem 1.5rem',
        background: '#f5f5f5',
        borderTop: '2px solid #ddd',
        fontSize: '0.85rem',
        color: '#666'
      }}>
        <strong>Rules:</strong> Must own all properties in color group (monopoly) to build.
        Houses must be built evenly. Hotels require 4 houses. Sell for 50% refund.
        Cannot mortgage if any property in group has improvements. Cannot build if any property in group is mortgaged.
      </div>
    </div>
  );
}
