# svg-generator.py
# Run: python3 svg-generator.py
# Reads Properties.csv -> writes board.svg

import csv

CELL = 100
GRID = 11
SIZE = CELL * GRID

MARGIN = 60        # true “outer” margin on each side
LR_EXTRA = 45      # extra width for left/right tiles (outward)
TOP_EXTRA = 24     # extra height for top-row tiles (upward)
BAR = 18           # property colour bar thickness

CSV_FILE = "Properties.csv"
OUT_FILE = "board.svg"

SHOW_PRICE_RENT = True
SHOW_NUMBER_IN_TITLE = True
NUMBER_ON_OWN_LINE = True   # keep space number on its own line

property_groups = [
  [1, 2],
  [6, 7, 9],
  [11, 13, 14],
  [16, 17, 18],
  [21, 22, 24],
  [26, 28, 29],
  [31, 33, 34],
  [37, 39],
]

group_colors = [
  "#E63946",
  "#F4A261",
  "#E9C46A",
  "#2A9D8F",
  "#457B9D",
  "#3A0CA3",
  "#7B2CBF",
  "#6C757D",
]

type_bg = {
  "START": "#E8F5E9",
  "REST": "#F1F3F5",
  "CHANCE": "#FFF7CC",
  "WELFARE": "#E6FCF5",
  "PENALTY": "#FFE3E3",
  "TRANSPORT": "#F3F0FF",
  "UTILITY": "#E7F5FF",
  "PROPERTY": "#FFFFFF",
}

TRANSPORT_NAMES = {"TransPerth","Warwick Train Station","Rottnest Express","Perth Airport"}
UTILITY_NAMES   = {"Synergy","Alinta Gas"}

# Board/viewport sizing so the left edge stays visible
BOARD_WIDTH  = SIZE + 2 * LR_EXTRA
BOARD_HEIGHT = SIZE + TOP_EXTRA      # top row extends outward
SVG_WIDTH  = BOARD_WIDTH  + 2 * MARGIN
SVG_HEIGHT = BOARD_HEIGHT + 2 * MARGIN

BASE_X = MARGIN + LR_EXTRA           # origin for (gx,gy) grid
BASE_Y = MARGIN + TOP_EXTRA

def detect_type(name: str) -> str:
  n = name.strip().lower()
  if "start/payday" in n or n == "start":
    return "START"
  if "chance" in n:
    return "CHANCE"
  if "welfare centre" in n:
    return "WELFARE"
  if "visit jail" in n or "rest home" in n:
    return "REST"
  if "income tax" in n or "mortgage payment" in n:
    return "PENALTY"
  if "police arrest" in n or "imprison" in n:
    return "PENALTY"
  if name.strip() in TRANSPORT_NAMES:
    return "TRANSPORT"
  if name.strip() in UTILITY_NAMES:
    return "UTILITY"
  return "PROPERTY"

def parse_money(x):
  if x is None:
    return None
  s = str(x).strip()
  if not s:
    return None
  s = s.replace("$","").replace(",","")
  try:
    return float(s)
  except ValueError:
    return None

def money_str(v):
  if v is None:
    return None
  if abs(v - round(v)) < 1e-9:
    return f"${int(round(v))}"
  return f"${v:.2f}"

def read_spaces_from_csv(path: str):
  rows = []
  with open(path, newline="", encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    _header = next(reader, None)
    for r in reader:
      if not r:
        continue
      idx = None
      idx_pos = None
      for j in range(min(5, len(r))):
        cell = r[j].strip()
        if not cell:
          continue
        try:
          v = int(cell)
          if 0 <= v <= 39:
            idx = v
            idx_pos = j
            break
        except ValueError:
          pass
      if idx is None:
        continue
      name_pos = idx_pos + 1
      if name_pos >= len(r):
        continue
      name = r[name_pos].strip()
      sale_price = parse_money(r[name_pos + 1] if len(r) > name_pos + 1 else None)
      rent1 = parse_money(r[name_pos + 2] if len(r) > name_pos + 2 else None)
      rows.append({
        "idx": idx,
        "name": name,
        "type": detect_type(name),
        "sale_price": sale_price,
        "rent1": rent1,
      })

  spaces = [None] * 40
  for row in rows:
    spaces[row["idx"] - 0] = row

  missing = [i + 1 for i, v in enumerate(spaces) if v is None]
  if missing:
    raise ValueError(f"Missing space rows for indices: {missing}")
  return spaces

def border_positions():
  pos = []
  for x in range(10, -1, -1): pos.append((x, 10))
  for y in range(9, -1, -1): pos.append((0, y))
  for x in range(1, 11): pos.append((x, 0))
  for y in range(1, 10): pos.append((10, y))
  assert len(pos) == 40
  return pos

def get_group_color(idx0):
  for gi, members in enumerate(property_groups):
    if idx0 in members:
      return group_colors[gi]
  return None

def side_for_cell(gx, gy):
  if gy == 10: return "BOTTOM"
  if gx == 0:  return "LEFT"
  if gy == 0:  return "TOP"
  if gx == 10: return "RIGHT"
  return "CENTER"

def text_side_for_cell(gx, gy):
  # For corners (Start, Go To Jail) we want the same alignment as other right-column cells.
  if gx == 10:
    return "RIGHT"
  if gx == 0:
    return "LEFT"
  return side_for_cell(gx, gy)

def space_bbox(gx, gy):
  px = BASE_X + gx * CELL
  py = BASE_Y + gy * CELL
  w = CELL
  h = CELL
  if gx == 0:
    px -= LR_EXTRA
    w += LR_EXTRA
  elif gx == 10:
    w += LR_EXTRA
  if gy == 0:
    py -= TOP_EXTRA
    h += TOP_EXTRA
  return px, py, w, h

def wrap_label(text, max_chars=18, max_lines=4):
  words = str(text).split()
  lines, cur = [], ""
  for w in words:
    nxt = (cur + " " + w).strip()
    if len(nxt) <= max_chars:
      cur = nxt
    else:
      if cur:
        lines.append(cur)
      cur = w
  if cur:
    lines.append(cur)
  return lines[:max_lines]

def text_block(x, y, lines, side, font_size=12):
  tx = x + BAR + 10 if side == "RIGHT" else x + 8
  ty = y + 32
  out = [f'<text x="{tx}" y="{ty}" font-family="Arial" font-size="{font_size}" fill="#111">']
  dy = 0
  for line in lines:
    out.append(f'<tspan x="{tx}" y="{ty+dy}">{line}</tspan>')
    dy += font_size + 2
  out.append("</text>")
  return "\n".join(out)

def lines_for_space(space_row, side):
  idx = space_row["idx"]
  name = space_row["name"]
  typ = space_row["type"]
  sale = space_row["sale_price"]
  rent1 = space_row["rent1"]

  max_chars = 18 if side in {"TOP","BOTTOM"} else 22
  lines = []
  if SHOW_NUMBER_IN_TITLE:
    if NUMBER_ON_OWN_LINE:
      lines.append(str(idx))
      lines.extend(wrap_label(name, max_chars=max_chars, max_lines=3))
    else:
      title = f"{idx}: {name}"
      lines.extend(wrap_label(title, max_chars=max_chars, max_lines=3))
  else:
    lines.extend(wrap_label(name, max_chars=max_chars, max_lines=3))

  if SHOW_PRICE_RENT:
    if typ in {"PROPERTY","TRANSPORT","UTILITY"}:
      if sale and sale > 0:
        lines.append(f"Buy {money_str(sale)}")
      if rent1:
        lines.append(f"Rent {money_str(rent1)}")
    elif sale and sale != 0:
      if sale < 0:
        lines.append(f"Pay {money_str(abs(sale))}")
      else:
        lines.append(f"Collect {money_str(sale)}")

  return lines[:6]

def rect(x, y, w, h, fill, stroke="#333", sw=2):
  return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'

def main():
  spaces = read_spaces_from_csv(CSV_FILE)
  positions = border_positions()

  svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">']

  inner_x = BASE_X + CELL
  inner_y = BASE_Y + CELL
  inner_size = SIZE - 2 * CELL
  svg.append(rect(inner_x, inner_y, inner_size, inner_size, "#FFFFFF", sw=2))

  for i0, (space, (gx, gy)) in enumerate(zip(spaces, positions)):
    x, y, w, h = space_bbox(gx, gy)
    bar_side = side_for_cell(gx, gy)
    text_side = text_side_for_cell(gx, gy)
    typ = space["type"]

    svg.append(rect(x, y, w, h, type_bg.get(typ, "#FFFFFF"), sw=2))

    if typ == "PROPERTY":
      gcol = get_group_color(i0)
      if gcol:
        if bar_side == "BOTTOM":
          svg.append(rect(x, y, w, BAR, gcol, sw=2))
        elif bar_side == "TOP":
          svg.append(rect(x, y + h - BAR, w, BAR, gcol, sw=2))
        elif bar_side == "LEFT":
          svg.append(rect(x + w - BAR, y, BAR, h, gcol, sw=2))
        elif bar_side == "RIGHT":
          svg.append(rect(x, y, BAR, h, gcol, sw=2))

    lines = lines_for_space(space, text_side)
    svg.append(text_block(x, y, lines, text_side))

  svg.append("</svg>")

  with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
  print(f"Wrote {OUT_FILE} from {CSV_FILE}")

if __name__ == "__main__":
  main()
