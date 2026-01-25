import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from app.api.routes import games, turns, ledger, jackpot, players, cards, decisions, lobby

app = FastAPI(title="MonopolyPerth API")

app.include_router(lobby.router, prefix="/games", tags=["lobby"])
app.include_router(games.router, prefix="/games", tags=["games"])
app.include_router(turns.router, prefix="/games/{game_id}/turns", tags=["turns"])
app.include_router(ledger.router, prefix="/games/{game_id}/ledger", tags=["ledger"])
app.include_router(jackpot.router, prefix="/games/{game_id}/jackpot", tags=["jackpot"])
app.include_router(decisions.router, prefix="/games/{game_id}", tags=["decisions"])
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