import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException


def require_admin_key(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> None:
    """Gate a write route behind a shared secret.

    Reads ADMIN_API_KEY at call time (not import time) so it can vary per-test
    and per-deploy without restarting the process. Fails closed: an unset env
    var rejects every request rather than allowing them through.
    """
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key or not x_admin_key or not secrets.compare_digest(x_admin_key, admin_key):
        raise HTTPException(status_code=401, detail="Missing or invalid admin key")
