"""ADR-003 Phase 4 — differential parity: Nest (:3101) vs FastAPI (:3102).

Two Docker Postgres clones (Prisma migrate on each, no dual-write), mirrored HTTP
corpus, normalized compare of status / JSON key-set / nullability / error shape /
critical headers. Report JSON is evidence for the QA parity matrix (§1 critical).

Run:  uv run python differential/run_parity.py   (from apps/api-python)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import httpx
import jwt as pyjwt

REPO = Path(__file__).resolve().parents[3]
API_TS = REPO / "apps" / "api"
API_PY = REPO / "apps" / "api-python"
REPORT_DIR = REPO / "docs" / "qa" / "differential"

sys.path.insert(0, str(API_PY / "tests"))
sys.path.insert(0, str(API_PY / "src"))

from pg_harness import migrate_database, start_docker_postgres, stop_docker_postgres  # noqa: E402

JWT_SECRET = "parity-secret-0123456789abcdef"
NEST_PORT = 3101
PY_PORT = 3102
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
UUID_SUB_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
SIG_RE = re.compile(r"^[a-f0-9]{64}$")


class Server:
    def __init__(self, name: str, base: str, database_url: str, storage: Path) -> None:
        self.name = name
        self.base = base
        self.database_url = database_url
        self.storage = storage
        self.process: subprocess.Popen | None = None


def _normalize_url(value: str) -> dict:
    parsed = urlparse(value)
    params = sorted(pair.split("=", 1)[0] for pair in parsed.query.split("&") if pair)
    path = UUID_SUB_RE.sub("<uuid>", parsed.path)
    return {"url": path, "params": params}


def _normalize(value, *, _jwt_key: str | None = None):
    if isinstance(value, dict):
        return {key: _normalize(item, _jwt_key=key) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, str):
        if UUID_RE.match(value):
            return "<uuid>"
        if ISO_RE.match(value):
            return "<iso8601>"
        if value.count(".") == 2 and value.startswith("eyJ"):
            claims = pyjwt.decode(value, options={"verify_signature": False})
            return {"jwt": {key: _normalize(val, _jwt_key=key) for key, val in sorted(claims.items())}}
        if value.startswith("http://") or value.startswith("https://"):
            return _normalize_url(value)
        if SIG_RE.match(value):
            return "<sig64>"
        if value.endswith(".bin") and UUID_RE.match(value[:-4]):
            return "<storage-key>"
        return value
    if isinstance(value, int) and _jwt_key in ("iat", "exp"):
        return "<epoch>"
    return value


def _headers_of(response: httpx.Response) -> dict:
    keep = ("content-type", "x-content-type-options")
    return {key: response.headers[key].split(";")[0] for key in keep if key in response.headers}


def _body_of(response: httpx.Response):
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return _normalize(response.json())
    return {"bytes_len": len(response.content), "content_type": content_type.split(";")[0]}


def compare(step: str, nest: httpx.Response, py: httpx.Response) -> list[str]:
    problems: list[str] = []
    if nest.status_code != py.status_code:
        problems.append(f"{step}: status {nest.status_code} != {py.status_code}")
        return problems
    nest_body, py_body = _body_of(nest), _body_of(py)
    if nest_body != py_body:
        problems.append(f"{step}: body\n  nest={json.dumps(nest_body, ensure_ascii=False)[:400]}\n  py={json.dumps(py_body, ensure_ascii=False)[:400]}")
    for header in ("content-type", "x-content-type-options"):
        left, right = _headers_of(nest).get(header), _headers_of(py).get(header)
        if left != right:
            problems.append(f"{step}: header {header} {left!r} != {right!r}")
    return problems


def _spawn_nest(server: Server) -> None:
    env = {
        **os.environ,
        "DATABASE_URL": server.database_url,
        "JWT_SECRET": JWT_SECRET,
        "API_PUBLIC_URL": server.base,
        "PORT": str(NEST_PORT),
        "STORAGE_ROOT": str(server.storage),
    }
    tsx = API_TS / "node_modules" / ".bin" / "tsx"
    command = [str(tsx), "src/main.ts"] if tsx.exists() else ["pnpm", "exec", "tsx", "src/main.ts"]
    server.process = subprocess.Popen(command, cwd=API_TS, env=env)


def _spawn_py(server: Server) -> None:
    env = {
        **os.environ,
        "DATABASE_URL": server.database_url,
        "JWT_SECRET": JWT_SECRET,
        "API_PUBLIC_URL": server.base,
        "STORAGE_ROOT": str(server.storage),
        "PYTHONPATH": str(API_PY / "src"),
    }
    uvicorn = API_PY / ".venv" / "bin" / "uvicorn"
    command = [str(uvicorn), "jplearn_api.main:app", "--port", str(PY_PORT)]
    server.process = subprocess.Popen(command, cwd=API_PY, env=env)


def _wait_ready(server: Server, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if server.process and server.process.poll() is not None:
            raise RuntimeError(f"{server.name} exited early with code {server.process.returncode}")
        try:
            if httpx.get(f"{server.base}/health", timeout=1).status_code == 200:
                return
        except httpx.TransportError:
            time.sleep(0.3)
    raise RuntimeError(f"{server.name} did not become ready on {server.base}")


def _stop(server: Server) -> None:
    if server.process and server.process.poll() is None:
        server.process.send_signal(signal.SIGTERM)
        try:
            server.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.process.kill()


async def _db(server: Server, operation):
    conn = await asyncpg.connect(server.database_url)
    try:
        return await operation(conn)
    finally:
        await conn.close()


async def _grant_admin(server: Server, email: str) -> None:
    await _db(
        server,
        lambda conn: conn.execute(
            'INSERT INTO user_roles (user_id, role) '
            "SELECT id, 'admin'::\"Role\" FROM users WHERE email = $1 ON CONFLICT DO NOTHING",
            email,
        ),
    )


async def _grant_teacher(server: Server, email: str) -> None:
    await _db(
        server,
        lambda conn: conn.execute(
            'INSERT INTO user_roles (user_id, role) '
            "SELECT id, 'teacher'::\"Role\" FROM users WHERE email = $1 ON CONFLICT DO NOTHING",
            email,
        ),
    )


async def _shift_started_at(server: Server, session_id: str, seconds: float) -> None:
    await _db(
        server,
        lambda conn: conn.execute(
            "UPDATE learning_sessions SET started_at = NOW() - make_interval(secs => $1) WHERE id = $2",
            seconds,
            session_id,
        ),
    )


async def _event_types(server: Server, session_id: str) -> list[str]:
    rows = await _db(
        server,
        lambda conn: conn.fetch("SELECT type FROM learning_events WHERE session_id = $1", session_id),
    )
    return [row["type"] for row in rows]


def _write_hls_bundle(server: Server, asset_id: str) -> None:
    directory = server.storage / "hls" / asset_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.m3u8").write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n#EXTINF:4.000,\nsegment-000.ts\n#EXT-X-ENDLIST\n",
        encoding="utf-8",
    )
    (directory / "segment-000.ts").write_bytes(b"fake ts segment")


class Pair:
    """Mirror the same request to both servers and record the responses."""

    def __init__(self, nest: httpx.Client, py: httpx.Client) -> None:
        self.nest = nest
        self.py = py
        self.problems: list[str] = []
        self.results: list[dict] = []

    def call(self, step: str, method: str, path: str, **kwargs):
        nest = self.nest.request(method, path, **kwargs)
        py = self.py.request(method, path, **kwargs)
        diffs = compare(step, nest, py)
        self.problems.extend(diffs)
        self.results.append(
            {
                "step": step,
                "status": nest.status_code,
                "pass": not diffs,
                "diffs": diffs,
            },
        )
        return nest, py


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def run_corpus(nest: Server, py: Server) -> list[dict]:
    problems: list[str] = []
    results: list[dict] = []

    with (
        httpx.Client(base_url=nest.base, timeout=15) as nest_http,
        httpx.Client(base_url=py.base, timeout=15) as py_http,
    ):
        pair = Pair(nest_http, py_http)

        # --- Auth (T-ID-001..003) ---
        email = f"diff-{int(time.time())}@example.com"
        reg_n, reg_p = pair.call(
            "auth/register",
            "POST",
            "/auth/register",
            json={"email": f"  {email.upper()}  ", "password": "password10"},
        )
        nest_tok, py_tok = reg_n.json()["access_token"], reg_p.json()["access_token"]

        pair.call("auth/login wrong password", "POST", "/auth/login", json={"email": email, "password": "wrong-wrong"})
        pair.call("auth/login", "POST", "/auth/login", json={"email": email, "password": "password10"})
        pair.call("GET /me no auth → 401", "GET", "/me")
        # /me needs each runtime's own token
        me_n = nest_http.get("/me", headers=_bearer(nest_tok))
        me_p = py_http.get("/me", headers=_bearer(py_tok))
        diffs = compare("GET /me (own token)", me_n, me_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "GET /me (own token)", "status": me_n.status_code, "pass": not diffs, "diffs": diffs})

        # --- Sessions / progress (T-SES, T-PRG, T-EVT) ---
        prog_n = nest_http.get("/progress", headers=_bearer(nest_tok))
        prog_p = py_http.get("/progress", headers=_bearer(py_tok))
        diffs = compare("GET /progress initial", prog_n, prog_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "GET /progress initial", "status": prog_n.status_code, "pass": not diffs, "diffs": diffs})

        pair.call("POST /sessions bad device", "POST", "/sessions", json={"device_class": "tv"})
        # unauthenticated progress → 401 both
        pair.call("GET /progress no auth", "GET", "/progress")

        sess_n = nest_http.post("/sessions", headers=_bearer(nest_tok), json={"device_class": "web"})
        sess_p = py_http.post("/sessions", headers=_bearer(py_tok), json={"device_class": "web"})
        diffs = compare("POST /sessions start", sess_n, sess_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "POST /sessions start", "status": sess_n.status_code, "pass": not diffs, "diffs": diffs})
        nest_session, py_session = sess_n.json()["id"], sess_p.json()["id"]

        asyncio.run(_shift_started_at(nest, nest_session, 120))
        asyncio.run(_shift_started_at(py, py_session, 120))
        end_n = nest_http.post(f"/sessions/{nest_session}/end", headers=_bearer(nest_tok))
        end_p = py_http.post(f"/sessions/{py_session}/end", headers=_bearer(py_tok))
        diffs = compare("POST /sessions/:id/end (2 min)", end_n, end_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "POST /sessions/:id/end (2 min)", "status": end_n.status_code, "pass": not diffs, "diffs": diffs})

        double_n = nest_http.post(f"/sessions/{nest_session}/end", headers=_bearer(nest_tok))
        double_p = py_http.post(f"/sessions/{py_session}/end", headers=_bearer(py_tok))
        diffs = compare("POST end twice → 400", double_n, double_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "POST end twice", "status": double_n.status_code, "pass": not diffs, "diffs": diffs})

        # event types recorded on both runtimes
        ev_n = asyncio.run(_event_types(nest, nest_session))
        ev_p = asyncio.run(_event_types(py, py_session))
        if sorted(ev_n) != sorted(ev_p):
            pair.problems.append(f"events: {sorted(ev_n)} != {sorted(ev_p)}")
            pair.results.append({"step": "learning_events types", "status": 0, "pass": False, "diffs": [f"{ev_n} != {ev_p}"]})
        else:
            pair.results.append({"step": "learning_events types", "status": 0, "pass": True, "diffs": []})

        # --- Flags (T-FLG-001, T-NFR-S2) ---
        pair.call("GET /flags no auth → 401", "GET", "/flags")
        flags_n = nest_http.get("/flags", headers=_bearer(nest_tok))
        flags_p = py_http.get("/flags", headers=_bearer(py_tok))
        diffs = compare("GET /flags default false", flags_n, flags_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "GET /flags default false", "status": flags_n.status_code, "pass": not diffs, "diffs": diffs})

        patch_n = nest_http.patch(
            "/staff/flags",
            headers=_bearer(nest_tok),
            json={"speaking_enabled": True, "l1_subtitles_enabled": False, "grammar_enabled": False, "flashcards_enabled": False},
        )
        patch_p = py_http.patch(
            "/staff/flags",
            headers=_bearer(py_tok),
            json={"speaking_enabled": True, "l1_subtitles_enabled": False, "grammar_enabled": False, "flashcards_enabled": False},
        )
        diffs = compare("PATCH /staff/flags as learner → 403", patch_n, patch_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "PATCH /staff/flags learner 403", "status": patch_n.status_code, "pass": not diffs, "diffs": diffs})

        # --- Catalog authz (T-ID-004) ---
        cat_n = nest_http.post(
            "/staff/catalog",
            headers=_bearer(nest_tok),
            json={"topic_id": "t1", "ci_level": 0, "duration_seconds": 10, "media_type": "video", "visual_support": "high", "title_internal": "x"},
        )
        cat_p = py_http.post(
            "/staff/catalog",
            headers=_bearer(py_tok),
            json={"topic_id": "t1", "ci_level": 0, "duration_seconds": 10, "media_type": "video", "visual_support": "high", "title_internal": "x"},
        )
        diffs = compare("POST /staff/catalog learner → 403", cat_n, cat_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "POST /staff/catalog learner 403", "status": cat_n.status_code, "pass": not diffs, "diffs": diffs})

        # --- FR-NEG 404s ---
        for path in ("/flashcards", "/grammar", "/grammar/lessons", "/vocabulary", "/translations"):
            neg_n = nest_http.get(path, headers=_bearer(nest_tok))
            neg_p = py_http.get(path, headers=_bearer(py_tok))
            diffs = compare(f"GET {path} → 404", neg_n, neg_p)
            pair.problems.extend(diffs)
            pair.results.append({"step": f"FR-NEG {path}", "status": neg_n.status_code, "pass": not diffs, "diffs": diffs})

        # --- Admin flows: catalog + media + HLS (T-CAT, T-CMS, T-NFR-P2) ---
        admin_email = f"admin-{int(time.time())}@example.com"
        nest_admin = nest_http.post("/auth/register", json={"email": admin_email, "password": "password10"})
        py_admin = py_http.post("/auth/register", json={"email": admin_email, "password": "password10"})
        pair.results.append(
            {
                "step": "auth/register admin",
                "status": nest_admin.status_code,
                "pass": not compare("auth/register admin", nest_admin, py_admin),
                "diffs": compare("auth/register admin", nest_admin, py_admin),
            },
        )
        pair.problems.extend(compare("auth/register admin", nest_admin, py_admin))
        asyncio.run(_grant_admin(nest, admin_email))
        asyncio.run(_grant_admin(py, admin_email))
        asyncio.run(_grant_teacher(nest, admin_email))
        asyncio.run(_grant_teacher(py, admin_email))
        nest_admin_tok, py_admin_tok = nest_admin.json()["access_token"], py_admin.json()["access_token"]

        for server in (nest, py):
            asyncio.run(
                _db(
                    server,
                    lambda conn: conn.execute(
                        "INSERT INTO topics (id, label_internal) VALUES ('daily_home','daily_home') ON CONFLICT DO NOTHING",
                    ),
                ),
            )

        create_n = nest_http.post(
            "/staff/catalog",
            headers=_bearer(nest_admin_tok),
            json={"topic_id": "daily_home", "ci_level": 0, "duration_seconds": 30, "media_type": "video", "visual_support": "high", "title_internal": "diff-item"},
        )
        create_p = py_http.post(
            "/staff/catalog",
            headers=_bearer(py_admin_tok),
            json={"topic_id": "daily_home", "ci_level": 0, "duration_seconds": 30, "media_type": "video", "visual_support": "high", "title_internal": "diff-item"},
        )
        diffs = compare("POST /staff/catalog admin → 201", create_n, create_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "POST /staff/catalog admin 201", "status": create_n.status_code, "pass": not diffs, "diffs": diffs})
        nest_item, py_item = create_n.json()["id"], create_p.json()["id"]

        # publish before media → 400 both
        qa_n = nest_http.post(f"/staff/catalog/{nest_item}/submit-qa", headers=_bearer(nest_admin_tok))
        qa_p = py_http.post(f"/staff/catalog/{py_item}/submit-qa", headers=_bearer(py_admin_tok))
        diffs = compare("submit-qa", qa_n, qa_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "submit-qa", "status": qa_n.status_code, "pass": not diffs, "diffs": diffs})

        pub_n = nest_http.post(f"/staff/catalog/{nest_item}/publish", headers=_bearer(nest_admin_tok))
        pub_p = py_http.post(f"/staff/catalog/{py_item}/publish", headers=_bearer(py_admin_tok))
        diffs = compare("publish without media → 400", pub_n, pub_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "publish without media 400", "status": pub_n.status_code, "pass": not diffs, "diffs": diffs})

        up_n = nest_http.post(
            f"/staff/catalog/{nest_item}/media",
            headers=_bearer(nest_admin_tok),
            files={"file": ("tiny.mp4", b"tiny media", "video/mp4")},
        )
        up_p = py_http.post(
            f"/staff/catalog/{py_item}/media",
            headers=_bearer(py_admin_tok),
            files={"file": ("tiny.mp4", b"tiny media", "video/mp4")},
        )
        diffs = compare("POST media upload → 201", up_n, up_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "POST media upload 201", "status": up_n.status_code, "pass": not diffs, "diffs": diffs})
        nest_asset, py_asset = up_n.json()["id"], up_p.json()["id"]

        pub2_n = nest_http.post(f"/staff/catalog/{nest_item}/publish", headers=_bearer(nest_admin_tok))
        pub2_p = py_http.post(f"/staff/catalog/{py_item}/publish", headers=_bearer(py_admin_tok))
        diffs = compare("publish with media → 200", pub2_n, pub2_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "publish with media 200", "status": pub2_n.status_code, "pass": not diffs, "diffs": diffs})

        # learner catalog list sees the published item with same public key-set
        list_n = nest_http.get("/catalog", headers=_bearer(nest_tok))
        list_p = py_http.get("/catalog", headers=_bearer(py_tok))
        item_n = next((i for i in list_n.json()["items"] if i["id"] == nest_item), None)
        item_p = next((i for i in list_p.json()["items"] if i["id"] == py_item), None)
        if item_n is None or item_p is None:
            diffs = [f"published item missing: nest={item_n is not None} py={item_p is not None}"]
        else:
            diffs = compare("GET /catalog published item", httpx.Response(200, json=item_n), httpx.Response(200, json=item_p))
        pair.problems.extend(diffs)
        pair.results.append({"step": "GET /catalog published item shape", "status": list_n.status_code, "pass": not diffs, "diffs": diffs})

        # media stream: Bearer + signed URL + expired sig
        stream_n = nest_http.get(f"/media/{nest_asset}", headers=_bearer(nest_tok))
        stream_p = py_http.get(f"/media/{py_asset}", headers=_bearer(py_tok))
        diffs = compare("GET /media Bearer", stream_n, stream_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "GET /media Bearer", "status": stream_n.status_code, "pass": not diffs, "diffs": diffs})

        signed_n = urlparse(item_n["playback_url"]) if item_n else None
        signed_p = urlparse(item_p["playback_url"]) if item_p else None
        if signed_n and signed_p:
            sig_n = nest_http.get(f"{signed_n.path}?{signed_n.query}")
            sig_p = py_http.get(f"{signed_p.path}?{signed_p.query}")
            diffs = compare("GET /media via signed URL", sig_n, sig_p)
            pair.problems.extend(diffs)
            pair.results.append({"step": "GET /media signed URL", "status": sig_n.status_code, "pass": not diffs, "diffs": diffs})

        bad_n = nest_http.get(f"/media/{nest_asset}?exp=1&sig={'ab' * 32}")
        bad_p = py_http.get(f"/media/{py_asset}?exp=1&sig={'ab' * 32}")
        diffs = compare("GET /media expired sig → 401", bad_n, bad_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "GET /media expired sig 401", "status": bad_n.status_code, "pass": not diffs, "diffs": diffs})

        # HLS: register before bundle → 400; then write bundle, register → 201, serve + rewrite
        hls_n = nest_http.post(f"/staff/media/{nest_asset}/hls", headers=_bearer(nest_admin_tok))
        hls_p = py_http.post(f"/staff/media/{py_asset}/hls", headers=_bearer(py_admin_tok))
        diffs = compare("register HLS without manifest → 400", hls_n, hls_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "register HLS missing manifest 400", "status": hls_n.status_code, "pass": not diffs, "diffs": diffs})

        _write_hls_bundle(nest, nest_asset)
        _write_hls_bundle(py, py_asset)
        reg2_n = nest_http.post(f"/staff/media/{nest_asset}/hls", headers=_bearer(nest_admin_tok))
        reg2_p = py_http.post(f"/staff/media/{py_asset}/hls", headers=_bearer(py_admin_tok))
        diffs = compare("register HLS → 201", reg2_n, reg2_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "register HLS 201", "status": reg2_n.status_code, "pass": not diffs, "diffs": diffs})

        man_n = nest_http.get(f"/media/{nest_asset}/hls/index.m3u8", headers=_bearer(nest_tok))
        man_p = py_http.get(f"/media/{py_asset}/hls/index.m3u8", headers=_bearer(py_tok))
        diffs = compare("GET manifest (Bearer, no rewrite)", man_n, man_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "GET manifest Bearer", "status": man_n.status_code, "pass": not diffs, "diffs": diffs})

        hls_url_n = urlparse(reg2_n.json()["hls_url"])
        hls_url_p = urlparse(reg2_p.json()["hls_url"])
        sman_n = nest_http.get(f"{hls_url_n.path}?{hls_url_n.query}")
        sman_p = py_http.get(f"{hls_url_p.path}?{hls_url_p.query}")
        line_n = next((l for l in sman_n.text.split("\n") if l.strip() and not l.strip().startswith("#")), "")
        line_p = next((l for l in sman_p.text.split("\n") if l.strip() and not l.strip().startswith("#")), "")
        rewrite_ok = bool(re.match(r"^segment-000\.ts\?exp=\d+&sig=[a-f0-9]{64}$", line_n)) and bool(
            re.match(r"^segment-000\.ts\?exp=\d+&sig=[a-f0-9]{64}$", line_p),
        )
        pair.results.append({"step": "manifest rewrite exp+sig", "status": sman_n.status_code, "pass": rewrite_ok, "diffs": [] if rewrite_ok else [f"{line_n!r} vs {line_p!r}"]})
        if not rewrite_ok:
            pair.problems.append(f"manifest rewrite: {line_n!r} vs {line_p!r}")

        seg_n = nest_http.get(f"/media/{nest_asset}/hls/{line_n}")
        seg_p = py_http.get(f"/media/{py_asset}/hls/{line_p}")
        diffs = compare("GET segment via rewritten URI", seg_n, seg_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "GET segment via signed URI", "status": seg_n.status_code, "pass": not diffs, "diffs": diffs})

        trav_n = nest_http.get(f"/media/{nest_asset}/hls/..%2Fsecret.m3u8", headers=_bearer(nest_tok))
        trav_p = py_http.get(f"/media/{py_asset}/hls/..%2Fsecret.m3u8", headers=_bearer(py_tok))
        diffs = compare("HLS traversal → 400", trav_n, trav_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "HLS traversal 400", "status": trav_n.status_code, "pass": not diffs, "diffs": diffs})

        miss_n = nest_http.get(f"/media/{nest_asset}/hls/segment-999.ts", headers=_bearer(nest_tok))
        miss_p = py_http.get(f"/media/{py_asset}/hls/segment-999.ts", headers=_bearer(py_tok))
        diffs = compare("HLS missing segment → 404", miss_n, miss_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "HLS missing 404", "status": miss_n.status_code, "pass": not diffs, "diffs": diffs})

        # --- Logout invalidates old token (T-ID-003) ---
        out_n = nest_http.post("/auth/logout", headers=_bearer(nest_tok))
        out_p = py_http.post("/auth/logout", headers=_bearer(py_tok))
        diffs = compare("POST /auth/logout → 204", out_n, out_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "logout 204", "status": out_n.status_code, "pass": not diffs, "diffs": diffs})

        me2_n = nest_http.get("/me", headers=_bearer(nest_tok))
        me2_p = py_http.get("/me", headers=_bearer(py_tok))
        diffs = compare("GET /me after logout → 401", me2_n, me2_p)
        pair.problems.extend(diffs)
        pair.results.append({"step": "me after logout 401", "status": me2_n.status_code, "pass": not diffs, "diffs": diffs})

    return pair.results


NEST_RETIRED_HINT = (
    "apps/api is gone: Nest was retired by ADR-004 after this harness recorded "
    "40/40 parity (docs/qa/differential/2026-09-04T071945Z-parity.json). "
    "To re-run the comparison, check out commit 7a05e62 (or a worktree of it) "
    "where apps/api still exists."
)


def main() -> int:
    if not (API_TS / "src" / "main.ts").exists():
        print(NEST_RETIRED_HINT, file=sys.stderr)
        return 2

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    report_path = REPORT_DIR / f"{stamp}-parity.json"

    projects = [f"jplearn-diff-nest-{os.getpid()}", f"jplearn-diff-py-{os.getpid()}"]
    storage = Path(tempfile.mkdtemp(prefix="jplearn-diff-storage-"))
    nest_storage, py_storage = storage / "nest", storage / "py"
    nest_storage.mkdir(parents=True)
    py_storage.mkdir(parents=True)

    servers: list[Server] = []
    exit_code = 1
    try:
        nest_db = start_docker_postgres(projects[0])
        py_db = start_docker_postgres(projects[1])
        nest = Server("nest", f"http://127.0.0.1:{NEST_PORT}", nest_db, nest_storage)
        py = Server("python", f"http://127.0.0.1:{PY_PORT}", py_db, py_storage)
        servers = [nest, py]
        _spawn_nest(nest)
        _spawn_py(py)
        _wait_ready(nest)
        _wait_ready(py)

        results = run_corpus(nest, py)
        failed = [row for row in results if not row["pass"]]
        report = {
            "generated_at": stamp,
            "servers": {"nest": NEST_PORT, "python": PY_PORT},
            "steps": len(results),
            "failed_steps": len(failed),
            "results": results,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        for row in results:
            mark = "PASS" if row["pass"] else "DIFF"
            print(f"[{mark}] {row['step']} (status {row['status']})")
            for diff in row["diffs"]:
                print(f"    {diff}")
        print(f"\n{len(results) - len(failed)}/{len(results)} steps identical. Report: {report_path}")
        exit_code = 0 if not failed else 1
    finally:
        for server in servers:
            _stop(server)
        for project in projects:
            stop_docker_postgres(project)
        shutil.rmtree(storage, ignore_errors=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
