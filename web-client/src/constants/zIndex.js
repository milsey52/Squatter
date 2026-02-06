/**
 * Standardized z-index values for modal layering.
 * Use these constants instead of hardcoded values to maintain consistency.
 */

export const Z_INDEX = {
  // Board elements (1-10)
  BOARD_ELEMENT: 1,
  BOARD_OVERLAY: 5,
  CARD_SECTION: 10,

  // Overlay panels (100s) - can be interacted with during gameplay
  PANEL: 100,
  PANEL_BANKRUPTCY: 10001, // Raised during bankruptcy to be above modals

  // Persistent UI elements (1000s)
  LOGOUT_BUTTON: 1001,
  TRADE_BANNER: 1000,

  // Normal game modals (2000s)
  MODAL: 2000,           // Purchase, auction, jail, worth, turn order
  MODAL_JAIL_OPTIONS: 2001,

  // Important modals (3000s)
  MODAL_SUSPENDED: 3000,
  MODAL_CARD: 3000,
  MODAL_RENT: 3000,

  // Bankruptcy flow (4000s)
  MODAL_BANKRUPTCY: 4000,
  MODAL_JAIL_BANKRUPTCY: 4001, // Jail options during bankruptcy

  // Game over (5000s)
  GAME_OVER: 5000,

  // Top-level popups (6000s)
  POPUP_CARD_DETAILS: 6000,
};
