// /home/max/programs/MonopolyPerth/web-client/src/Board.jsx
import boardSVG from "/board.svg";
import { boardIndexToPixel, GRID_POSITIONS } from "./boardLayout";

const CELL = 100;
const TOKEN_SIZE = 28;
const TOKEN_COLORS = ["#ff595e", "#8ac926", "#1982c4", "#ffca3a", "#ff924c", "#7d5ba6"];

// Convert space_id to board index for GRID_POSITIONS array
function toBoardIndex(spaceId) {
  // PostgreSQL database uses 0-based indexing matching GRID_POSITIONS array
  if (spaceId === undefined || spaceId === null || spaceId < 0) return 0;
  return spaceId % GRID_POSITIONS.length;
}

export default function Board({ players = [], currentPlayerId, propertyImprovements = {} }) {
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
        const boardIdx = toBoardIndex(player.current_space_id);
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
              color: "#fff",
              fontWeight: 600,
              fontSize: "0.9rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              // THIS IS THE CHANGE:
              left: left + centerOffset + offsetIndex * 14,
              top: top + centerOffset + 0.5 * TOKEN_SIZE + offsetIndex * 14,
              boxShadow: isActive
                ? "0 0 10px 3px rgba(255,215,0,0.8)"
                : "0 0 4px rgba(0,0,0,0.3)",
              border: isActive
                ? "2px solid #ffd700"
                : "2px solid rgba(0,0,0,0.2)",
              transition: "box-shadow 0.2s ease",
            }}
          >
            {player.player_name?.[0] ?? "?"}
          </div>
        );
      })}

      {/* Render houses and hotels on properties */}
      {Object.entries(propertyImprovements).map(([spaceId, improvement]) => {
        if (!improvement || (improvement.improvement_level === 0 && !improvement.has_hotel)) {
          return null;
        }

        // Map space_id directly to board index (no adjustment needed)
        const spaceIdNum = parseInt(spaceId);
        const boardIdx = toBoardIndex(spaceIdNum);
        const { left, top } = boardIndexToPixel(boardIdx);

        // Display hotel (RED)
        if (improvement.has_hotel) {
          return (
            <div
              key={`improvement-${spaceId}`}
              style={{
                position: "absolute",
                left: left + 5,
                top: top + 5,
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
            // Position from RHS: House 0 at pixels 75-100, House 1 at 50-75, House 2 at 25-50, House 3 at 0-25
            const houseLeft = left + CELL - ((i + 1) * houseWidth);
            return (
              <div
                key={`improvement-${spaceId}-${i}`}
                style={{
                  position: "absolute",
                  left: houseLeft,
                  top: top + 5,
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