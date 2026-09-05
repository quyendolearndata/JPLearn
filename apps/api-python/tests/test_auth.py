from uuid import uuid4

from jplearn_api.tokens import decode_access_token


def _email() -> str:
    return f"u{uuid4().hex[:12]}@example.com"


def test_register_login_me_hides_password_hash(live_client):
    email = _email()
    registered = live_client.post(
        "/auth/register",
        json={"email": f"  {email.upper()}  ", "password": "password10"},
    )
    assert registered.status_code == 201, registered.text
    body = registered.json()
    assert body["access_token"]
    assert body["user"]["email"] == email
    assert body["user"]["roles"] == ["learner"]
    assert "passwordHash" not in body["user"]
    assert "password_hash" not in body["user"]

    payload = decode_access_token(body["access_token"], live_client.app.state.settings.jwt_secret)
    assert payload["sub"] == body["user"]["id"]
    assert payload["email"] == email
    assert payload["ver"] == 0
    assert payload["jti"]

    bad = live_client.post("/auth/login", json={"email": email, "password": "wrong-wrong"})
    assert bad.status_code == 401
    assert bad.json()["statusCode"] == 401
    assert "detail" not in bad.json()

    me = live_client.get("/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["roles"] == ["learner"]
    assert "passwordHash" not in me.json()


def test_login_issues_token_for_registered_user(live_client):
    email = _email()
    password = "password10"
    assert live_client.post("/auth/register", json={"email": email, "password": password}).status_code == 201

    login = live_client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = live_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["roles"] == ["learner"]


def test_logout_invalidates_every_token(live_client):
    email = _email()
    first = live_client.post("/auth/register", json={"email": email, "password": "password10"})
    second = live_client.post("/auth/login", json={"email": email, "password": "password10"})
    assert first.status_code == 201
    assert second.status_code == 200
    logout = live_client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {first.json()['access_token']}"},
    )
    assert logout.status_code == 204
    assert live_client.get(
        "/me",
        headers={"Authorization": f"Bearer {first.json()['access_token']}"},
    ).status_code == 401
    assert live_client.get(
        "/me",
        headers={"Authorization": f"Bearer {second.json()['access_token']}"},
    ).status_code == 401


def test_duplicate_email_is_409(live_client):
    email = _email()
    payload = {"email": email, "password": "password10"}
    assert live_client.post("/auth/register", json=payload).status_code == 201
    again = live_client.post("/auth/register", json=payload)
    assert again.status_code == 409
    assert again.json()["message"] == "Email already registered"


def test_me_without_bearer_is_401(live_client):
    response = live_client.get("/me")
    assert response.status_code == 401
    assert "detail" not in response.json()
    assert response.json()["statusCode"] == 401


def test_no_auth_payload_leaks_credentials(live_client):
    """T-NFR-PR1 / NFR-PRIV-001 — credentials never reach a client payload.

    Scans raw response text rather than checking a key name, so a renamed or
    nested field cannot slip a hash through.
    """
    email = _email()
    registered = live_client.post("/auth/register", json={"email": email, "password": "password10"})
    login = live_client.post("/auth/login", json={"email": email, "password": "password10"})
    token = login.json()["access_token"]
    me = live_client.get("/me", headers={"Authorization": f"Bearer {token}"})

    for response in (registered, login, me):
        body = response.text
        for leak in ("argon2", "password_hash", "passwordHash", "token_version", "tokenVersion"):
            assert leak not in body, f"{response.request.url} leaked {leak}"

    assert set(me.json()) == {"id", "email", "roles"}


def test_short_password_is_400(live_client):
    response = live_client.post(
        "/auth/register",
        json={"email": _email(), "password": "short"},
    )
    assert response.status_code == 400
    assert "detail" not in response.json()
    assert "Password must be at least 10 characters" in str(response.json()["message"])
