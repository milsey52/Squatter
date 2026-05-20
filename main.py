import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text
from app.api.routes import games, turns, ledger, cards, decisions, lobby, events, trades, station
from app.api.deps import get_session

app = FastAPI(title="Squatter API", redirect_slashes=False)

app.include_router(lobby.router, prefix="/games", tags=["lobby"])
app.include_router(events.router, prefix="/games", tags=["events"])
app.include_router(games.router, prefix="/games", tags=["games"])
app.include_router(turns.router, prefix="/games/{game_id}/turns", tags=["turns"])
app.include_router(ledger.router, prefix="/games/{game_id}/ledger", tags=["ledger"])
app.include_router(decisions.router, prefix="/games/{game_id}", tags=["decisions"])
app.include_router(trades.router, prefix="/games/{game_id}/trades", tags=["trades"])
app.include_router(station.router, prefix="/games/{game_id}/station", tags=["station"])
app.include_router(cards.router)

# CORS configuration
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
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/board.svg")
    async def serve_board_svg():
        svg_path = os.path.join(os.path.dirname(__file__), "web-client", "public", "board.svg")
        if os.path.exists(svg_path):
            return FileResponse(svg_path, media_type="image/svg+xml")
        return FileResponse(os.path.join(static_dir, "board.svg"), media_type="image/svg+xml")

    @app.get("/")
    async def serve_root():
        index_path = os.path.join(static_dir, "index.html")
        # Force browsers to re-validate index.html every load so the freshly-built
        # bundle (with a new content-hashed filename) is picked up without a hard refresh.
        return FileResponse(
            index_path,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )


# Admin endpoint to reset all game data
@app.get("/admin/reset-all-games")
def reset_all_games(session=Depends(get_session)):
    session.execute(text(
        "TRUNCATE TABLE turn_order_rolls, trade_sessions, "
        "card_draws, stock_card_draws, movements, transactions, pending_actions, "
        "turns, paddocks, stud_ram_states, game_rules, game_sessions, game_players, games, users "
        "CASCADE"
    ))
    session.commit()
    return {"status": "ok", "message": "All game data deleted"}


# Admin endpoint to reseed static data
@app.get("/admin/reseed-static-data")
def reseed_static_data(session=Depends(get_session)):
    from scripts.seed_static_data import seed_spaces, seed_stock_cards, seed_tucker_bag_cards

    session.execute(text("TRUNCATE TABLE cards, stock_cards, spaces CASCADE"))
    session.commit()

    seed_spaces(session)
    seed_stock_cards(session)
    seed_tucker_bag_cards(session)

    return {"status": "ok", "message": "Static data reseeded"}
