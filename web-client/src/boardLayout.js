// Squatter board layout: 44 spaces in clockwise order
// Board is 12x12 grid (4 sides of 11 spaces + 4 corners)
// Side layout: 11 spaces per side (including corners)
// Bottom: spaces 0-10 (right to left)
// Left: spaces 11-21 (bottom to top)
// Top: spaces 22-32 (left to right)
// Right: spaces 33-43 (top to bottom)

const CELL = 90;
const MARGIN = 50;

// 44 board positions in clockwise order (0 = Wool Sale at bottom-right corner)
export const GRID_POSITIONS = [
  // Bottom row (right to left): spaces 0-10
  { x: 11, y: 11 }, // 0  Wool Sale (Start)
  { x: 10, y: 11 },
  { x: 9, y: 11 },
  { x: 8, y: 11 },
  { x: 7, y: 11 },
  { x: 6, y: 11 },
  { x: 5, y: 11 },
  { x: 4, y: 11 },
  { x: 3, y: 11 },
  { x: 2, y: 11 },
  { x: 1, y: 11 },
  // Left column (bottom to top): spaces 11-21
  { x: 0, y: 11 },
  { x: 0, y: 10 },
  { x: 0, y: 9 },
  { x: 0, y: 8 },
  { x: 0, y: 7 },
  { x: 0, y: 6 },
  { x: 0, y: 5 },
  { x: 0, y: 4 },
  { x: 0, y: 3 },
  { x: 0, y: 2 },
  { x: 0, y: 1 },
  // Top row (left to right): spaces 22-32
  { x: 0, y: 0 },
  { x: 1, y: 0 },
  { x: 2, y: 0 },
  { x: 3, y: 0 },
  { x: 4, y: 0 },
  { x: 5, y: 0 },
  { x: 6, y: 0 },
  { x: 7, y: 0 },
  { x: 8, y: 0 },
  { x: 9, y: 0 },
  { x: 10, y: 0 },
  // Right column (top to bottom): spaces 33-43
  { x: 11, y: 0 },
  { x: 11, y: 1 },
  { x: 11, y: 2 },
  { x: 11, y: 3 },
  { x: 11, y: 4 },
  { x: 11, y: 5 },
  { x: 11, y: 6 },
  { x: 11, y: 7 },
  { x: 11, y: 8 },
  { x: 11, y: 9 },
  { x: 11, y: 10 },
];

export function boardIndexToPixel(idx) {
  if (idx < 0 || idx >= GRID_POSITIONS.length) {
    return { left: 0, top: 0 };
  }
  const { x, y } = GRID_POSITIONS[idx];
  return {
    left: MARGIN + x * CELL,
    top: MARGIN + y * CELL,
  };
}
