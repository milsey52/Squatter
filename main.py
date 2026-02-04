import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import games, turns, ledger, jackpot, players, cards, decisions, lobby, events, trades, properties, bankruptcy

app = FastAPI(title="MonopolyPerth API")

app.include_router(lobby.router, prefix="/games", tags=["lobby"])
app.include_router(events.router, prefix="/games", tags=["events"])
app.include_router(games.router, prefix="/games", tags=["games"])
app.include_router(turns.router, prefix="/games/{game_id}/turns", tags=["turns"])
app.include_router(ledger.router, prefix="/games/{game_id}/ledger", tags=["ledger"])
app.include_router(jackpot.router, prefix="/games/{game_id}/jackpot", tags=["jackpot"])
app.include_router(decisions.router, prefix="/games/{game_id}", tags=["decisions"])
app.include_router(trades.router, prefix="/games/{game_id}/trades", tags=["trades"])
app.include_router(properties.router, prefix="/games/{game_id}", tags=["properties"])
app.include_router(bankruptcy.router)
app.include_router(players.router)
app.include_router(cards.router)

# CORS configuration from environment variable
# Set CORS_ORIGINS as comma-separated list, e.g., "http://localhost:5173,http://localhost:3000"
# Defaults to localhost:5173 for development
cors_origins_str = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Serve static frontend files (built from web-client)
static_dir = os.path.join(os.path.dirname(__file__), "web-client", "dist")
if os.path.exists(static_dir):
    # Mount static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    # Serve board.svg
    @app.get("/board.svg")
    async def serve_board_svg():
        svg_path = os.path.join(os.path.dirname(__file__), "web-client", "public", "board.svg")
        if os.path.exists(svg_path):
            return FileResponse(svg_path, media_type="image/svg+xml")
        return FileResponse(os.path.join(static_dir, "board.svg"), media_type="image/svg+xml")

    # Serve index.html at root
    @app.get("/")
    async def serve_root():
        index_path = os.path.join(static_dir, "index.html")
        return FileResponse(index_path)