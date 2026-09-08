from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError

ALGORITHM = "HS256"
EXPIRES = timedelta(hours=8)


def sign_access_token(*, user_id: str, email: str, ver: int, secret: str) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "ver": ver,
        "iat": int(now.timestamp()),
        "exp": int((now + EXPIRES).timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("ver"), int):
        raise InvalidTokenError("missing sub/ver")
    return payload
