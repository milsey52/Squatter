"""Timestamp convention: naive UTC.

The DateTime columns are TIMESTAMP WITHOUT TIME ZONE, so application code
standardizes on naive UTC instead of datetime.now() (server-local time,
which differs between a dev box and the UTC production container).
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
