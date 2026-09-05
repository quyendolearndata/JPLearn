import re

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

# node-argon2 defaults (see docs/qa/vectors/argon2.json): argon2id m=65536 p=4 t=3
HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# libargon2 only parses PHC params as m,t,p. node-argon2 emits m,p,t.
_PHC = re.compile(
    r"^(\$(?:argon2(?:id|i|d))\$v=\d+\$)([^$]+)(\$.+)$",
)


def normalize_phc(encoded: str) -> str:
    match = _PHC.match(encoded)
    if match is None:
        return encoded
    params = dict(part.split("=", 1) for part in match.group(2).split(",") if "=" in part)
    if not {"m", "t", "p"} <= params.keys():
        return encoded
    return f"{match.group(1)}m={params['m']},t={params['t']},p={params['p']}{match.group(3)}"


def hash_password(plain: str) -> str:
    return HASHER.hash(plain)


def verify_password(encoded: str, plain: str) -> bool:
    try:
        return HASHER.verify(normalize_phc(encoded), plain)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False
