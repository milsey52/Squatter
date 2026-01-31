// /home/max/programs/MonopolyPerth/web-client/src/Board.jsx
import boardSVG from "/board.svg";
import { boardIndexToPixel, GRID_POSITIONS } from "./boardLayout";

const CELL = 100;
const TOKEN_SIZE = 28;
const TOKEN_COLORS = ["#ff595e", "#8ac926", "#1982c4", "#ffca3a", "#ff924c", "#7d5ba6"];

// Convert from 1-based space_id to 0-based board index
function toBoardIndex(spaceId) {
  // Database uses 1-based space_id, but GRID_POSITIONS array is 0-based
  if (spaceId === undefined || spaceId === null || spaceId < 1) return 0;
  return (spaceId - 1) % GRID_POSITIONS.length;
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

        const boardIdx = toBoardIndex(parseInt(spaceId));
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

        // Display houses (BLUE)
        if (improvement.improvement_level > 0) {
          const houseCount = improvement.improvement_level;
          return (
            <div
              key={`improvement-${spaceId}`}
              style={{
                position: "absolute",
                left: left + 5,
                top: top + 5,
                fontSize: "1.2rem",
                pointerEvents: "none",
                display: "flex",
                gap: "2px",
                background: "#0066ff",
                color: "#fff",
                padding: "2px 4px",
                borderRadius: "4px",
                border: "2px solid #fff",
                boxShadow: "0 2px 4px rgba(0,0,0,0.3)",
                zIndex: 1
              }}
              title={`${houseCount} House${houseCount > 1 ? 's' : ''}`}
            >
              {Array.from({ length: houseCount }).map((_, i) => (
                <span key={i}>🏠</span>
              ))}
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}