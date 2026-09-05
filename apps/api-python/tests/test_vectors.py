import json
import re
from pathlib import Path

from jplearn_api.password import hash_password, verify_password
from jplearn_api.signed_url import hmac_hex, verify_media_sig
from jplearn_api.tokens import decode_access_token

VECTORS = Path(__file__).resolve().parents[3] / "docs" / "qa" / "vectors"


def test_jwt_vector_verifies_with_test_secret():
    file = json.loads((VECTORS / "jwt-claims.json").read_text(encoding="utf-8"))
    payload = decode_access_token(file["token"], file["secret"])
    claims = file["claims"]
    assert payload["sub"] == claims["sub"]
    assert payload["email"] == claims["email"]
    assert payload["ver"] == claims["ver"]
    assert payload["jti"] == claims["jti"]
    assert payload["exp"] == claims["exp"]


def test_argon2_vector_verifies_node_hash_and_python_hash_roundtrip():
    file = json.loads((VECTORS / "argon2.json").read_text(encoding="utf-8"))
    assert verify_password(file["encoded"], file["plaintext"]) is True
    assert verify_password(file["encoded"], "wrong-password") is False
    encoded = hash_password(file["plaintext"])
    assert "m=65536" in encoded and "t=3" in encoded and "p=4" in encoded
    assert encoded.startswith("$argon2id$v=19$")
    assert verify_password(encoded, file["plaintext"]) is True


def test_hmac_media_url_vector_matches_node():
    file = json.loads((VECTORS / "hmac-media-url.json").read_text(encoding="utf-8"))
    openapi_sig = re.compile(r"^[a-f0-9]{64}$")
    for case in file["cases"]:
        computed = hmac_hex(case["secret"], case["assetId"], case["exp"])
        if len(case["expect"]["sig"]) == 64:
            assert computed == case["expect"]["sig"].lower()
        assert (
            verify_media_sig(
                asset_id=case["assetId"],
                exp=case["exp"],
                sig=case["expect"]["sig"],
                secret=case["secret"],
                now_sec=case["nowSec"],
            )
            is case["expect"]["valid"]
        )
        if case["expect"].get("openapi_sig_pattern") is False:
            assert openapi_sig.match(case["expect"]["sig"]) is None
