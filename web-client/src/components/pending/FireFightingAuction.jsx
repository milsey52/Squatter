import { useState } from "react";
import { useModalChrome } from "./useModalChrome";
import { ErrorLine } from "./shared";

/* Fire Fighting Equipment auction: the drawer declined, the card goes to
   the highest bidder among the other players. */
export default function FireFightingAuction({ gameId, sessionToken, userId, data, players, onResolved }) {
  const chrome = useModalChrome({ gameId, sessionToken, onResolved });
  const { modalStyle, btnStyle, submitting, error, doAction } = chrome;
  const [auctionBid, setAuctionBid] = useState(0);

  const myPlayer = players.find(p => p.user_id === userId);
  const myPlayerId = myPlayer?.game_player_id ?? null;
  const eligible = data.eligible_players || [];
  const declined = data.declined || [];
  const currentBid = data.current_bid;
  const currentBidderId = data.current_bidder_id;
  const startingPrice = data.starting_price ?? 350;
  const minBid = (currentBid === null || currentBid === undefined)
    ? startingPrice
    : currentBid + 1;
  const isEligible = eligible.some(ep => ep.id === myPlayerId);
  const hasDeclined = declined.includes(myPlayerId);
  const isHighBidder = currentBidderId === myPlayerId;
  const canAct = isEligible && !hasDeclined && !isHighBidder;
  const effectiveBid = auctionBid && auctionBid >= minBid ? auctionBid : minBid;

  return (
    <div style={modalStyle}>
      <h2 style={{ margin: '0 0 0.5rem', color: '#d32f2f' }}>
        Fire Fighting Equipment — Auction
      </h2>
      <p style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: '#555' }}>
        {data.card_title || 'Fire Fighting Equipment'}
      </p>
      <p style={{ margin: '0 0 0.75rem', fontSize: '0.8rem', color: '#666', fontStyle: 'italic' }}>
        Drawer declined. Card is now offered to the other players by auction —
        highest bid wins. Minimum opening bid: ${startingPrice}.
      </p>
      <div style={{ padding: '0.6rem', background: '#FFF8E1', border: '1px solid #FFB300', borderRadius: 6, marginBottom: '0.75rem' }}>
        {currentBid !== null && currentBid !== undefined ? (
          <div style={{ fontSize: '0.95rem' }}>
            <strong>Current bid:</strong> ${currentBid} by {data.current_bidder_name}
          </div>
        ) : (
          <div style={{ fontSize: '0.95rem', color: '#666' }}>No bids yet.</div>
        )}
      </div>
      {/* Status panel showing who's in / out */}
      <div style={{ fontSize: '0.8rem', color: '#555', marginBottom: '0.75rem' }}>
        {eligible.map(ep => {
          const status =
            ep.id === currentBidderId ? 'leading'
            : declined.includes(ep.id) ? 'declined'
            : 'undecided';
          const color =
            status === 'leading' ? '#388e3c'
            : status === 'declined' ? '#b71c1c'
            : '#666';
          return (
            <span key={ep.id} style={{ marginRight: 10, color }}>
              {ep.name} ({status})
            </span>
          );
        })}
      </div>
      {!isEligible ? (
        <p style={{ fontStyle: 'italic', color: '#666' }}>
          You declined the card; waiting for the auction to complete.
        </p>
      ) : hasDeclined ? (
        <p style={{ fontStyle: 'italic', color: '#666' }}>
          You declined. Waiting for the auction to complete.
        </p>
      ) : isHighBidder ? (
        <p style={{ fontWeight: 'bold', color: '#2e7d32' }}>
          You are leading at ${currentBid}. Waiting for other players.
        </p>
      ) : (
        <>
          <div style={{ marginTop: '0.5rem' }}>
            <label>Bid: <input type="number" min={minBid}
              value={effectiveBid}
              onChange={e => setAuctionBid(Number(e.target.value))}
              style={{ width: 90, marginLeft: 8 }} /></label>
            <span style={{ marginLeft: 12, fontSize: '0.78rem', color: '#666' }}>
              min ${minBid}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
            <button style={btnStyle('#4caf50')} disabled={submitting || !canAct}
              onClick={() => doAction('decisions/fire-fighting-auction-bid', { bid: effectiveBid })}>
              BID ${effectiveBid}
            </button>
            <button style={btnStyle('#666')} disabled={submitting || !canAct}
              onClick={() => doAction('decisions/fire-fighting-auction-decline')}>
              DECLINE
            </button>
          </div>
        </>
      )}
      <ErrorLine error={error} />
    </div>
  );
}
