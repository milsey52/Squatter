// /home/max/programs/MonopolyPerth/web-client/src/boardLayout.js

const CELL = 100;
const MARGIN = 60;
const LR_EXTRA = 45;
const TOP_EXTRA = 24;

// 40 board positions in clockwise order (0 = Start/Payday) matching the SVG layout
export const GRID_POSITIONS = [
  { x: 10, y: 10 }, // 0  Start/Payday
  { x: 9, y: 10 },
  { x: 8, y: 10 },
  { x: 7, y: 10 },
  { x: 6, y: 10 },
  { x: 5, y: 10 },
  { x: 4, y: 10 },
  { x: 3, y: 10 },
  { x: 2, y: 10 },
  { x: 1, y: 10 },
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
  { x: 10, y: 1 },
  { x: 10, y: 2 },
  { x: 10, y: 3 },
  { x: 10, y: 4 },
  { x: 10, y: 5 },
  { x: 10, y: 6 },
  { x: 10, y: 7 },
  { x: 10, y: 8 },
  { x: 10, y: 9 },
];

export function boardIndexToPixel(idx) {
  const { x, y } = GRID_POSITIONS[idx];
  let left = MARGIN + x * CELL;
  let top = MARGIN + y * CELL;

  if (x === 0) left -= LR_EXTRA;    // left column sticks out
  if (y === 0) top -= TOP_EXTRA;    // top row sticks upward

  return { left, top };
}