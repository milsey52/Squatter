import boardSVG from "/board.svg";
import { boardIndexToPixel, GRID_POSITIONS } from "./boardLayout";

// Cache-buster: bump when board.svg content changes so stuck client caches
// (which the previous no-cache header can't retroactively invalidate) fetch
// the new file. The query string makes the URL unique so the browser treats
// it as a fresh resource.
const BOARD_SVG_VERSION = 4;

const CELL = 90;
const TOKEN_SIZE = 26;
const MARKER_SIZE = 22;
const TOKEN_COLORS = ["#ff595e", "#8ac926", "#1982c4", "#ffca3a", "#ff924c", "#7d5ba6"];
const TOKEN_TEXT_COLORS = ["#fff", "#000", "#fff", "#000", "#fff", "#fff"];

function toBoardIndex(spaceId) {
  if (spaceId === undefined || spaceId === null || spaceId < 0) return 0;
  return spaceId % GRID_POSITIONS.length;
}

// One <svg> shape per marker, with the player initial centred inside.
function MarkerShape({ kind, color, textColor, initial }) {
  const s = MARKER_SIZE;
  const stroke = "rgba(0,0,0,0.55)";
  const textProps = {
    fill: textColor, fontWeight: 700, fontSize: 11,
    textAnchor: "middle", dominantBaseline: "central",
    fontFamily: "Arial, sans-serif",
  };
  if (kind === "square") {
    return (
      <svg width={s} height={s} viewBox="0 0 22 22">
        <rect x="1" y="1" width="20" height="20" rx="2"
              fill={color} stroke={stroke} strokeWidth="1.5" />
        <text x="11" y="12" {...textProps}>{initial}</text>
      </svg>
    );
  }
  if (kind === "triangle") {
    return (
      <svg width={s} height={s} viewBox="0 0 22 22">
        <polygon points="11,2 21,20 1,20"
                 fill={color} stroke={stroke} strokeWidth="1.5"
                 strokeLinejoin="round" />
        <text x="11" y="15" {...textProps}>{initial}</text>
      </svg>
    );
  }
  if (kind === "haystack") {
    // Stylised dome with two horizontal binding lines.
    return (
      <svg width={s} height={s} viewBox="0 0 22 22">
        <path d="M 2 20 Q 11 1 20 20 Z"
              fill={color} stroke={stroke} strokeWidth="1.5"
              strokeLinejoin="round" />
        <line x1="4.5" y1="14" x2="17.5" y2="14"
              stroke={stroke} strokeWidth="0.8" />
        <line x1="6.5" y1="9" x2="15.5" y2="9"
              stroke={stroke} strokeWidth="0.8" />
        <text x="11" y="16" {...textProps}>{initial}</text>
      </svg>
    );
  }
  return null;
}

function collectMarkers(players) {
  const markers = [];
  players.forEach((p, idx) => {
    const color = TOKEN_COLORS[idx % TOKEN_COLORS.length];
    const textColor = TOKEN_TEXT_COLORS[idx % TOKEN_TEXT_COLORS.length];
    const initial = (p.player_name?.[0] || "?").toUpperCase();
    if (p.drought_marker_space_id !== null && p.drought_marker_space_id !== undefined) {
      markers.push({
        playerId: p.game_player_id, kind: "square",
        spaceId: p.drought_marker_space_id,
        color, textColor, initial,
        label: `${p.player_name} — Drought circuit`,
      });
    }
    const src = p.restock_block_source;
    const blk = p.restock_block_marker_space_id;
    if (blk !== null && blk !== undefined) {
      if (src === "lucerne_flea") {
        markers.push({
          playerId: p.game_player_id, kind: "triangle",
          spaceId: blk, color, textColor, initial,
          label: `${p.player_name} — Lucerne Flea circuit`,
        });
      } else if (src === "grass_fire") {
        markers.push({
          playerId: p.game_player_id, kind: "haystack",
          spaceId: blk, color, textColor, initial,
          label: `${p.player_name} — Grass Fire circuit`,
        });
      }
    }
  });
  return markers;
}

export default function Board({ players = [], currentPlayerId, animatedPositions = {} }) {
  const stackMap = players.reduce((acc, player) => {
    const idx = toBoardIndex(player.current_space_id);
    if (!acc[idx]) acc[idx] = [];
    acc[idx].push(player.game_player_id);
    return acc;
  }, {});

  // Markers cluster on their home cell — group so we can offset duplicates.
  const markers = collectMarkers(players);
  const markersByCell = markers.reduce((acc, m) => {
    const idx = toBoardIndex(m.spaceId);
    if (!acc[idx]) acc[idx] = [];
    acc[idx].push(m);
    return acc;
  }, {});

  return (
    <div style={{ position: "relative", width: 1130, height: 1130 }}>
      <img src={`${boardSVG}?v=${BOARD_SVG_VERSION}`} alt="Board" style={{ width: "100%", height: "100%" }} />

      {/* Circuit markers — pinned to the cell where the event began. */}
      {Object.entries(markersByCell).flatMap(([idxStr, cellMarkers]) => {
        const idx = parseInt(idxStr, 10);
        const { left, top } = boardIndexToPixel(idx);
        return cellMarkers.map((m, i) => {
          // Cluster: column wraps every 2 markers so they don't overflow the cell.
          const col = i % 2;
          const row = Math.floor(i / 2);
          const x = left + 4 + col * (MARKER_SIZE + 2);
          const y = top + 18 + row * (MARKER_SIZE + 2);
          return (
            <div key={`${m.playerId}-${m.kind}-${idx}`}
                 title={m.label}
                 style={{ position: "absolute", left: x, top: y,
                          width: MARKER_SIZE, height: MARKER_SIZE,
                          pointerEvents: "auto" }}>
              <MarkerShape kind={m.kind} color={m.color}
                           textColor={m.textColor} initial={m.initial} />
            </div>
          );
        });
      })}

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
