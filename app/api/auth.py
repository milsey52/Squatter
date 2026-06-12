"""Authentication middleware for session token verification."""
from app.utils.time import utc_now
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from app import models
from app.api import deps


def verify_session_token(
    authorization: str = Header(None),
    session: Session = Depends(deps.get_session)
) -> tuple[int, int]:
    """
    Verify session token from Authorization header and return user_id and game_id.

    Args:
        authorization: Authorization header (format: "Bearer <token>")
        session: Database session

    Returns:
        Tuple of (user_id, game_id)

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected 'Bearer <token>'"
        )

    token = authorization.replace("Bearer ", "")

    # Query session token
    game_session = session.query(models.GameSession).filter_by(
        session_token=token
    ).first()

    if not game_session:
        raise HTTPException(
            status_code=401,
            detail="Invalid session token"
        )

    # Check expiration
    if game_session.expires_at < utc_now():
        raise HTTPException(
            status_code=401,
            detail="Session token has expired"
        )

    return game_session.user_id, game_session.game_id


def get_current_user_and_game(
    auth_data: tuple[int, int] = Depends(verify_session_token)
) -> tuple[int, int]:
    """
    Convenience dependency that returns the authenticated user_id and game_id.

    Args:
        auth_data: Tuple from verify_session_token

    Returns:
        Tuple of (user_id, game_id)
    """
    return auth_data
