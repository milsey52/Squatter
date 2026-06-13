// Maps a board space's type to the manual section it should open at.
// Kept separate from Manual.jsx so that file only exports a component
// (React Fast Refresh requires component-only modules).
export const SPACE_TYPE_TO_SECTION = {
  wool_sale: "wool-sale",
  stock_sale: "stock-sale",
  stud_ram: "stud-rams",
  stud_ram_dies: "stud-rams",
  tucker_bag: "tucker-bag",
  expense: "expenses",
  flood_damage: "expenses",
  local_drought: "local-drought",
  bore_dries_up: "bore-dries-up",
  local_rain: "local-rain",
  visiting_town: "visiting-town",
};
