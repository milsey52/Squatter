// /home/max/programs/MonopolyPerth/web-client/src/Board.jsx
import boardSVG from "/board.svg";
import { boardIndexToPixel, GRID_POSITIONS } from "./boardLayout";

const CELL = 100;
const TOKEN_SIZE = 28;
const TOKEN_COLORS = ["#ff595e", "#8ac926", "#1982c4", "#ffca3a", "#ff924c", "#7d5ba6"];
// Text colors chosen for readability on each background
const TOKEN_TEXT_COLORS = ["#fff", "#000", "#fff", "#000", "#fff", "#fff"];

// Convert space_id to board index for GRID_POSITIONS array
function toBoardIndex(spaceId) {
  // PostgreSQL database uses 0-based indexing matching GRID_POSITIONS array
  if (spaceId === undefined || spaceId === null || spaceId < 0) return 0;
  return spaceId % GRID_POSITIONS.length;
}

export default function Board({ players = [], currentPlayerId, propertyImprovements = {}, animatedPositions = {} }) {
  // Prepare per-space stacks so overlapping tokens get offset
  const stackMap = players.reduce((acc, player) => {
    const idx = toBoardIndex(player.current_space_id);
    if (!acc[idx]) acc[idx] = [];
    acc[idx].push(player.game_player_id);
    return acc;
  }, {});

  return (
    <div style={{ position: "relative", width: 1300, height: 1300 }}>
      <img src={boardSVG} alt="Board" style={{ width: "100%", height: "100%" }} />

      {players.map((player, idx) => {
        // Use animated position if available, otherwise use database position
        const displayPosition = animatedPositions[player.game_player_id] !== undefined
          ? animatedPositions[player.game_player_id]
          : player.current_space_id;

        const boardIdx = toBoardIndex(displayPosition);
        const { left, top } = boardIndexToPixel(boardIdx);
        const stack = stackMap[boardIdx] || [];
        const offsetIndex = stack.indexOf(player.game_player_id);
        const isActive = player.game_player_id === currentPlayerId;

        // Center the token in the cell — no more hardcoded offsets!
        const centerOffset = CELL / 2 - TOKEN_SIZE / 2;

        return (
          <div
            key={player.game_player_id}
            title={player.player_name}
            style={{
              position: "absolute",
              width: TOKEN_SIZE,
              height: TOKEN_SIZE,
              borderRadius: "50%",
              background: TOKEN_COLORS[idx % TOKEN_COLORS.length],
              color: TOKEN_TEXT_COLORS[idx % TOKEN_TEXT_COLORS.length],
              fontWeight: 600,
              fontSize: "0.9rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              // THIS IS THE CHANGE:
              left: left + centerOffset + 5 + offsetIndex * 14,
              top: top + centerOffset + 10 + 0.5 * TOKEN_SIZE + offsetIndex * 14,
              boxShadow: isActive
                ? "0 0 10px 3px rgba(255,215,0,0.8)"
                : "0 0 4px rgba(0,0,0,0.3)",
              border: isActive
                ? "2px solid #ffd700"
                : "2px solid rgba(0,0,0,0.2)",
              // Add smooth transitions for position and box-shadow
              transition: "left 0.15s ease-out, top 0.15s ease-out, box-shadow 0.2s ease",
            }}
          >
            {player.player_name?.[0] ?? "?"}
          </div>
        );
      })}

      {/* Render houses and hotels on properties */}
      {Object.entries(propertyImprovements).map(([boardIndex, improvement]) => {
        if (!improvement || (improvement.improvement_level === 0 && !improvement.has_hotel)) {
          return null;
        }

        // propertyImprovements is now keyed by board_index (0-39)
        const boardIdx = parseInt(boardIndex);
        const { left, top } = boardIndexToPixel(boardIdx);

        // Display hotel (RED)
        if (improvement.has_hotel) {
          // Special positioning adjustments by board region
          const isBottomRow = boardIdx >= 1 && boardIdx <= 9;
          const isTopRow = boardIdx >= 21 && boardIdx <= 30;
          const isLeftColumn = boardIdx >= 11 && boardIdx <= 19;
          const isRightColumn = boardIdx >= 31 && boardIdx <= 39;
          let hotelLeft = left + 5;
          if (isRightColumn) {
            hotelLeft = left + 5 - 70 + 250;  // Shift right for right column
          } else if (isLeftColumn) {
            hotelLeft = left + 5 + 5;  // Shift right for left column
          } else if (isBottomRow) {
            hotelLeft = left + 5 + 35;  // Shift right for bottom row
          } else if (isTopRow) {
            hotelLeft = left + 5 + 40;  // Shift right for top row
          }

          let hotelTop = top + 5;
          if (isBottomRow) {
            hotelTop = top + 5 + 145;
          } else if (isTopRow) {
            hotelTop = top + 5 + 27;
          } else if (isRightColumn) {
            hotelTop = top + 5 + 55;  // Shift down for right column
          } else if (isLeftColumn) {
            hotelTop = top + 5 + 50;  // Shift down for left column
          }
          return (
            <div
              key={`improvement-${boardIndex}`}
              style={{
                position: "absolute",
                left: hotelLeft,
                top: hotelTop,
                fontSize: "1.8rem",
                pointerEvents: "none",
                background: "#ff0000",
                color: "#fff",
                padding: "2px 6px",
                borderRadius: "4px",
                border: "2px solid #fff",
                boxShadow: "0 2px 4px rgba(0,0,0,0.3)",
                fontWeight: "bold",
                zIndex: 1
              }}
              title="Hotel"
            >
              🏨
            </div>
          );
        }

        // Display houses (BLUE) - stack from right to left within property
        // Property is 8 units wide (8,7,6,5,4,3,2,1 from left to right)
        // House 1: units 1-2 (rightmost), House 2: units 3-4, House 3: units 5-6, House 4: units 7-8 (leftmost)
        if (improvement.improvement_level > 0) {
          const houseCount = improvement.improvement_level;
          const houseWidth = 25; // Each house is 25px wide (2 units out of 8)
          return Array.from({ length: houseCount }).map((_, i) => {
            // Special positioning adjustments by board region
            const isBottomRow = boardIdx >= 1 && boardIdx <= 9;
            const isTopRow = boardIdx >= 21 && boardIdx <= 30;
            const isLeftColumn = boardIdx >= 11 && boardIdx <= 19;
            const isRightColumn = boardIdx >= 31 && boardIdx <= 39;

            let houseLeft, houseTop;

            if (isLeftColumn || isRightColumn) {
              // Vertical stacking for left and right columns
              if (isRightColumn) {
                houseLeft = left + 5 - 70 + 250;  // Shift right for right column
                houseTop = top + 5 + 55 + (i * 20);  // Stack vertically with 55px offset and 20px spacing
              } else if (isLeftColumn) {
                houseLeft = left + 5 + 5;  // Shift right for left column
                houseTop = top + 5 + 50 + (i * 20);  // Stack vertically with 50px offset and 20px spacing
              }
            } else {
              // Horizontal stacking for top and bottom rows
              const baseLeft = left + CELL - ((i + 1) * houseWidth);
              houseLeft = baseLeft;
              if (isBottomRow) {
                houseLeft = baseLeft + 35;  // Shift right for bottom row
              } else if (isTopRow) {
                houseLeft = baseLeft + 40;  // Shift right for top row
              }
              houseTop = top + 5;
              if (isBottomRow) {
                houseTop = top + 5 + 145;
              } else if (isTopRow) {
                houseTop = top + 5 + 27;
              }
            }
            return (
              <div
                key={`improvement-${boardIndex}-${i}`}
                style={{
                  position: "absolute",
                  left: houseLeft,
                  top: houseTop,
                  fontSize: "0.9rem",
                  pointerEvents: "none",
                  background: "#0066ff",
                  color: "#fff",
                  padding: "1px 3px",
                  borderRadius: "3px",
                  border: "1px solid #fff",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                  zIndex: 1,
                  width: `${houseWidth}px`,
                  textAlign: "center"
                }}
                title={`House ${i + 1} of ${houseCount}`}
              >
                🏠
              </div>
            );
          });
        }

        return null;
      })}
    </div>
  );
}