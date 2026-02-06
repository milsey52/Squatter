import { useState } from 'react';
import { Z_INDEX } from '../constants/zIndex';

export default function RetainedCardPopup({ card, onClose }) {
  if (!card) return null;

  const bgColor = '#6a4c93'; // Purple color for retained cards

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: Z_INDEX.POPUP_CARD_DETAILS
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: '12px',
          padding: '2rem',
          maxWidth: '500px',
          width: '90%',
          boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            background: bgColor,
            color: '#fff',
            padding: '1rem',
            borderRadius: '8px',
            marginBottom: '1.5rem',
            textAlign: 'center'
          }}
        >
          <h2 style={{ margin: 0, fontSize: '1.5rem' }}>
            🃏 Retained Card
          </h2>
        </div>

        {/* Card Content */}
        <div
          style={{
            background: '#f9f9f9',
            border: `3px solid ${bgColor}`,
            borderRadius: '8px',
            padding: '1.5rem',
            marginBottom: '1.5rem',
            minHeight: '150px'
          }}
        >
          <h3
            style={{
              margin: '0 0 1rem 0',
              color: '#333',
              fontSize: '1.2rem',
              textAlign: 'center'
            }}
          >
            {card.title || card.name || 'Card'}
          </h3>
          <p
            style={{
              margin: 0,
              color: '#555',
              fontSize: '1rem',
              lineHeight: '1.5',
              textAlign: 'center'
            }}
          >
            {card.body_text || card.description || 'No description available'}
          </p>
        </div>

        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            width: '100%',
            padding: '1rem',
            background: bgColor,
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontSize: '1.1rem',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}
        >
          Close
        </button>
      </div>
    </div>
  );
}
