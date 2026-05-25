import boardSVG from "/board.svg";
import { boardIndexToPixel, GRID_POSITIONS } from "./boardLayout";

// Cache-buster: bump when board.svg content changes so stuck client caches
// (which the previous no-cache header can't retroactively invalidate) fetch
// the new file. The query string makes the URL unique so the browser treats
// it as a fresh resource.
const BOARD_SVG_VERSION = 3;

const CELL = 90;
const TOKEN_SIZE = 26;
const TOKEN_COLORS = ["#ff595e", "#8ac926", "#1982c4", "#ffca3a", "#ff924c", "#7d5ba6"];
const TOKEN_TEXT_COLORS = ["#fff", "#000", "#fff", "#000", "#fff", "#fff"];

function toBoardIndex(spaceId) {
  if (spaceId === undefined || spaceId === null || spaceId < 0) return 0;
  return spaceId % GRID_POSITIONS.length;
}

export default function Board({ players = [], currentPlayerId, animatedPositions = {} }) {
  const stackMap = players.reduce((acc, player) => {
    const idx = toBoardIndex(player.current_space_id);
    if (!acc[idx]) acc[idx] = [];
    acc[idx].push(player.game_player_id);
    return acc;
  }, {});

  return (
    <div style={{ position: "relative", width: 1130, height: 1130 }}>
      <img src={`${boardSVG}?v=${BOARD_SVG_VERSION}`} alt="Board" style={{ width: "100%", height: "100%" }} />

      {players.map((player, idx) => {
        const displayPosition = animatedPositions[player.game_player_id] !== undefined
          ? animatedPositions[player.game_player_id]
          : player.current_space_id;

        const boardIdx = toBoardIndex(displayPosition);
        const { left, top } = boardIndexToPixel(boardIdx);
        const stack = stackMap[boardIdx] || [];
        const offsetIndex = stack.indexOf(player.game_player_id);
        const isActive = player.game_player_id === currentPlayerId;

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
              fontSize: "0.85rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              left: left + centerOffset + offsetIndex * 12,
              top: top + centerOffset + TOKEN_SIZE * 0.5 + offsetIndex * 12,
              boxShadow: isActive
                ? "0 0 10px 3px rgba(255,215,0,0.8)"
                : "0 0 4px rgba(0,0,0,0.3)",
              border: isActive
                ? "2px solid #ffd700"
                : "2px solid rgba(0,0,0,0.2)",
              transition: "left 0.15s ease-out, top 0.15s ease-out, box-shadow 0.2s ease",
            }}
          >
            {player.player_name?.[0] ?? "?"}
          </div>
        );
      })}
    </div>
  );
}
