from __future__ import annotations

import hmac


def is_valid_token(expected_token: str, authorization_header: str | None) -> bool:
    """Compare le token en temps constant pour eviter les attaques par timing."""
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return False
    provided = authorization_header[len("Bearer "):]
    return hmac.compare_digest(provided.encode("utf-8"), expected_token.encode("utf-8"))
