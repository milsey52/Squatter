import FireFightingAuction from "./pending/FireFightingAuction";
import StockSaleDecision from "./pending/StockSaleDecision";
import StudRam from "./pending/StudRam";
import Expense from "./pending/Expense";
import WoolCheque from "./pending/WoolCheque";
import TuckerBagResult from "./pending/TuckerBagResults";
import DroughtEffects from "./pending/DroughtEffects";
import GenericInfo from "./pending/GenericInfo";
import { FireFightingOffer, HaystackOfferModal, DebtSettlement } from "./pending/Misc";

/* Thin dispatcher: picks the view for the current pending action. All the
   per-action UI lives in ./pending/ — one file per action family, sharing
   the chrome + action plumbing from ./pending/shared.jsx. */
export default function PendingActionModal({
  gameId, sessionToken, userId, pendingAction, players, onResolved,
  activePlayerHasHighStockPrices = false,
}) {
  if (!pendingAction) return null;

  const activePlayer = players.find(p => p.game_player_id === pendingAction.active_player_id);
  const isMyAction = !!(activePlayer && activePlayer.user_id === userId);
  const data = pendingAction.action_data || {};
  const t = pendingAction.action_type;

  // Rendered elsewhere, not as a centred modal:
  // - stock_sale_result / tucker_bag_drawn: board-anchored overlays (App.jsx)
  // - game_won: the celebratory banner on the board
  // - drought/tucker results that drew a Stock Sale card via haystack:
  //   board-anchored overlay
  if (t === 'stock_sale_result' || t === 'tucker_bag_drawn' || t === 'game_won') return null;
  if ((t === 'drought_effect' || t === 'tucker_bag_result') && data.stock_card_used) return null;

  const common = {
    gameId, sessionToken, userId, pendingAction, data, players,
    activePlayer, isMyAction, onResolved, activePlayerHasHighStockPrices,
  };

  switch (t) {
    case 'fire_fighting_auction':
      return <FireFightingAuction {...common} />;
    case 'stock_sale_decision':
      return <StockSaleDecision {...common} />;
    case 'stud_ram_purchase':
    case 'stud_fee_paid':
      return <StudRam {...common} />;
    case 'expense_payment':
      return <Expense {...common} />;
    case 'wool_cheque_paid':
      return <WoolCheque {...common} />;
    case 'tucker_bag_result':
      return <TuckerBagResult {...common} />;
    case 'drought_effect':
    case 'bore_dries_up_effect':
    case 'drought_all_stations_result':
      return <DroughtEffects {...common} />;
    case 'fire_fighting_offer':
      return <FireFightingOffer {...common} />;
    case 'haystack_offer':
      return <HaystackOfferModal {...common} />;
    case 'debt_settlement':
      return <DebtSettlement {...common} />;
    default:
      return <GenericInfo {...common} />;
  }
}
