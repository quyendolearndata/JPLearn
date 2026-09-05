#!/usr/bin/env python3
"""Reproducible HTTP-level Benchmark Runner for JPLearn API.

Runs workloads against native PostgreSQL backend using FastAPI TestClient:
- Auth: Register, Login, Token Verify
- Catalog: Full list (10 items), Filtered list (ci_level=0), Filtered list (empty)
- Sessions: Start session, End session, Full lifecycle
- Media Upload: 5MB streaming upload + storage promote + metadata transaction

Captures raw per-iteration latency samples, queries per request, and peak RSS memory.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from typing import Any
from datetime import UTC, datetime
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import statistics
import sys
import tempfile
import time


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    k = (len(data) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(data) - 1)
    return round(data[f] + (data[c] - data[f]) * (k - f), 3)


def compute_stats(samples_ms: list[float]) -> dict[str, Any]:
    s = sorted(samples_ms)
    return {
        "count": len(s),
        "raw_samples_ms": [round(x, 3) for x in samples_ms],
        "min": round(min(s), 3),
        "p50": percentile(s, 50),
        "p95": percentile(s, 95),
        "p99": percentile(s, 99),
        "max": round(max(s), 3),
        "mean": round(statistics.mean(s), 3),
    }


def get_peak_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if platform.system() == "Darwin":
        return round(usage.ru_maxrss / (1024 * 1024), 2)
    return round(usage.ru_maxrss / 1024, 2)


def run_bench(repo_dir: Path, out_path: Path, label: str) -> dict[str, Any]:
    app_dir = repo_dir / "apps" / "api-python"
    sys.path.insert(0, str(app_dir / "src"))
    sys.path.insert(0, str(app_dir / "tests"))

    from pg_harness import start_docker_postgres, stop_docker_postgres, seed_database
    from helpers import ensure_topics, grant_role, insert_media, register
    # Each revision's test harness owns its app import path (including pre-layout baselines).
    from conftest import _settings, create_app
    from fastapi.testclient import TestClient
    from sqlalchemy import event

    print("=" * 70)
    print(f"BENCHMARK RUN: {label}")
    print(f"Directory: {repo_dir}")
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print("=" * 70)

    project = f"jplearn-benchmark-{os.getpid()}"
    db_url = start_docker_postgres(project)
    print(f"Database: {db_url}")

    results = {
        "label": label,
        "metadata": {
            "tested_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir, text=True).strip(),
            "source_status": subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_dir, text=True).splitlines(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_sha256": hashlib.sha256(b"".join(
                str(p.relative_to(app_dir)).encode() + b"\0" + p.read_bytes()
                for p in sorted((app_dir / "src").rglob("*.py"))
            )).hexdigest(),
            "warmup_iterations": 5,
            "timestamp": datetime.now(UTC).isoformat(),
            "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "python": sys.version.split()[0],
            "database_url": db_url,
        },
        "metrics": {},
    }

    temp_storage = None
    try:
        seed_database(db_url)
        temp_storage = tempfile.mkdtemp(prefix=f"jplearn_bench_{label}_")
        os.environ["STORAGE_ROOT"] = temp_storage
        settings = _settings(db_url)
        app = create_app(settings)

        with TestClient(app) as client:
            ensure_topics(client)

            # Query counter interceptor
            query_counter = 0

            def count_query(conn, cursor, statement, parameters, context, executemany):
                nonlocal query_counter
                query_counter += 1

            engine = app.state.engine
            event.listen(engine.sync_engine, "before_cursor_execute", count_query)

            # 1. Auth Workload
            print("\n[1/4] Measuring Auth Latency (Register, Login, Token Verify)...")
            register_samples = []
            login_samples = []
            verify_samples = []

            for i in range(30):
                email = f"bench_user_{label}_{i}@example.com"
                password = "Password123!"

                t0 = time.perf_counter()
                reg_res = client.post("/auth/register", json={"email": email, "password": password})
                t1 = time.perf_counter()
                assert reg_res.status_code == 201
                register_samples.append((t1 - t0) * 1000)

                t2 = time.perf_counter()
                log_res = client.post("/auth/login", json={"email": email, "password": password})
                t3 = time.perf_counter()
                assert log_res.status_code == 200
                login_samples.append((t3 - t2) * 1000)
                token = log_res.json()["access_token"]

                t4 = time.perf_counter()
                p_res = client.get("/progress", headers={"Authorization": f"Bearer {token}"})
                t5 = time.perf_counter()
                assert p_res.status_code == 200
                verify_samples.append((t5 - t4) * 1000)

            register_samples = register_samples[5:]
            login_samples = login_samples[5:]
            verify_samples = verify_samples[5:]

            results["metrics"]["auth"] = {
                "register": compute_stats(register_samples),
                "login": compute_stats(login_samples),
                "token_verify_request": compute_stats(verify_samples),
            }
            print(f"  Login p50: {results['metrics']['auth']['login']['p50']} ms | p95: {results['metrics']['auth']['login']['p95']} ms")
            print(f"  Token Verify p50: {results['metrics']['auth']['token_verify_request']['p50']} ms")

            # Setup admin and learner for catalog & session tests
            admin_resp = register(client)
            admin_id = admin_resp.json()["user"]["id"]
            grant_role(client, admin_id, "admin")
            grant_role(client, admin_id, "teacher")
            admin_token = admin_resp.json()["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

            learner_resp = register(client)
            learner_token = learner_resp.json()["access_token"]
            learner_headers = {"Authorization": f"Bearer {learner_token}"}

            # 2. Catalog Workload (Populate items)
            print("\n[2/4] Measuring Catalog Queries (Full list, Filtered ci_level=0, Empty filter)...")
            for i in range(10):
                cat_body = {
                    "topic_id": "daily_home",
                    "ci_level": i % 3,
                    "duration_seconds": 30 + i,
                    "media_type": "video",
                    "visual_support": "high",
                    "title_internal": f"Catalog Item {i}",
                }
                c_res = client.post("/staff/catalog", headers=admin_headers, json=cat_body)
                assert c_res.status_code == 201
                item_id = c_res.json()["id"]
                insert_media(client, item_id)
                qa = client.post(f"/staff/catalog/{item_id}/submit-qa", headers=admin_headers)
                assert qa.status_code in (200, 201), qa.text
                published = client.post(f"/staff/catalog/{item_id}/publish", headers=admin_headers)
                assert published.status_code in (200, 201), published.text

            fixture = client.get("/catalog", headers=learner_headers)
            assert fixture.status_code == 200
            assert len(fixture.json()["items"]) == 10, "catalog fixture cardinality mismatch"

            catalog_all_samples = []
            catalog_filtered_samples = []
            catalog_empty_samples = []
            cat_all_queries = []
            cat_filt_queries = []

            for _ in range(45):
                query_counter = 0
                t0 = time.perf_counter()
                r_all = client.get("/catalog", headers=learner_headers)
                t1 = time.perf_counter()
                assert r_all.status_code == 200
                assert len(r_all.json()["items"]) == 10
                catalog_all_samples.append((t1 - t0) * 1000)
                cat_all_queries.append(query_counter)

                query_counter = 0
                t2 = time.perf_counter()
                r_filt = client.get("/catalog?ci_level=0", headers=learner_headers)
                t3 = time.perf_counter()
                assert r_filt.status_code == 200
                assert len(r_filt.json()["items"]) == 4
                catalog_filtered_samples.append((t3 - t2) * 1000)
                cat_filt_queries.append(query_counter)

                t4 = time.perf_counter()
                r_empty = client.get("/catalog?ci_level=4", headers=learner_headers)
                t5 = time.perf_counter()
                assert r_empty.status_code == 200
                assert r_empty.json()["items"] == []
                catalog_empty_samples.append((t5 - t4) * 1000)

            catalog_all_samples = catalog_all_samples[5:]
            catalog_filtered_samples = catalog_filtered_samples[5:]
            catalog_empty_samples = catalog_empty_samples[5:]
            cat_all_queries = cat_all_queries[5:]
            cat_filt_queries = cat_filt_queries[5:]

            results["metrics"]["catalog"] = {
                "catalog_all_10_items": {
                    "latency": compute_stats(catalog_all_samples),
                    "queries_per_req": round(statistics.mean(cat_all_queries), 1),
                    "raw_query_counts": cat_all_queries,
                },
                "catalog_filtered_ci0": {
                    "latency": compute_stats(catalog_filtered_samples),
                    "queries_per_req": round(statistics.mean(cat_filt_queries), 1),
                    "raw_query_counts": cat_filt_queries,
                },
                "catalog_filtered_empty": {
                    "latency": compute_stats(catalog_empty_samples),
                },
            }
            print(f"  Catalog All p50: {results['metrics']['catalog']['catalog_all_10_items']['latency']['p50']} ms | p95: {results['metrics']['catalog']['catalog_all_10_items']['latency']['p95']} ms")
            print(f"  Catalog Filtered p50: {results['metrics']['catalog']['catalog_filtered_ci0']['latency']['p50']} ms")

            # 3. Learning Sessions Workload
            print("\n[3/4] Measuring Learning Sessions Lifecycle (Start -> End -> Progress)...")
            sess_start_samples = []
            sess_end_samples = []
            sess_total_samples = []
            sess_queries = []

            for _ in range(30):
                query_counter = 0
                t0 = time.perf_counter()
                s_res = client.post("/sessions", headers=learner_headers, json={"device_class": "web"})
                t1 = time.perf_counter()
                assert s_res.status_code == 201
                sid = s_res.json()["id"]

                t2 = time.perf_counter()
                e_res = client.post(f"/sessions/{sid}/end", headers=learner_headers, json={})
                t3 = time.perf_counter()
                assert e_res.status_code == 200

                t4 = time.perf_counter()
                p_res = client.get("/progress", headers=learner_headers)
                t5 = time.perf_counter()
                assert p_res.status_code == 200

                sess_start_samples.append((t1 - t0) * 1000)
                sess_end_samples.append((t3 - t2) * 1000)
                sess_total_samples.append((t5 - t0) * 1000)
                sess_queries.append(query_counter)

            sess_start_samples = sess_start_samples[5:]
            sess_end_samples = sess_end_samples[5:]
            sess_total_samples = sess_total_samples[5:]
            sess_queries = sess_queries[5:]

            results["metrics"]["sessions"] = {
                "start": compute_stats(sess_start_samples),
                "end": compute_stats(sess_end_samples),
                "full_lifecycle": compute_stats(sess_total_samples),
                "queries_per_lifecycle": round(statistics.mean(sess_queries), 1),
                "raw_query_counts": sess_queries,
            }
            print(f"  Session Start p50: {results['metrics']['sessions']['start']['p50']} ms")
            print(f"  Session End p50: {results['metrics']['sessions']['end']['p50']} ms")
            print(f"  Session Lifecycle p50: {results['metrics']['sessions']['full_lifecycle']['p50']} ms")

            # 4. Media Upload Workload (5MB)
            print("\n[4/4] Measuring Media Upload (5MB chunked payload)...")
            payload_5mb = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + (b"B" * (5 * 1024 * 1024 - 24))
            upload_durations = []
            upload_queries = []
            rss_samples = []

            for i in range(15):
                cat_body = {
                    "topic_id": "daily_home",
                    "ci_level": 1,
                    "duration_seconds": 60,
                    "media_type": "video",
                    "visual_support": "high",
                    "title_internal": f"Upload Test Item {i}",
                }
                item_res = client.post("/staff/catalog", headers=admin_headers, json=cat_body)
                assert item_res.status_code == 201
                target_item = item_res.json()["id"]

                query_counter = 0
                t0 = time.perf_counter()
                up_res = client.post(
                    f"/staff/catalog/{target_item}/media",
                    headers=admin_headers,
                    files={"file": (f"bench_upload_{i}.mp4", BytesIO(payload_5mb), "video/mp4")},
                )
                t1 = time.perf_counter()
                assert up_res.status_code == 201
                upload_durations.append((t1 - t0) * 1000)
                upload_queries.append(query_counter)
                rss_samples.append(get_peak_rss_mb())

            upload_durations = upload_durations[5:]
            upload_queries = upload_queries[5:]
            rss_samples = rss_samples[5:]

            results["metrics"]["media_upload_5mb"] = {
                "duration": compute_stats(upload_durations),
                "queries_per_upload": round(statistics.mean(upload_queries), 1),
                "peak_rss_mb": max(rss_samples),
                "raw_query_counts": upload_queries,
                "raw_peak_rss_mb": rss_samples,
            }
            print(f"  Upload 5MB p50: {results['metrics']['media_upload_5mb']['duration']['p50']} ms | p95: {results['metrics']['media_upload_5mb']['duration']['p95']} ms")
            print(f"  Queries per upload: {results['metrics']['media_upload_5mb']['queries_per_upload']}")
            print(f"  Peak RSS: {results['metrics']['media_upload_5mb']['peak_rss_mb']} MB")

    finally:
        if project:
            print("\nTearing down temporary Docker PostgreSQL container...")
            stop_docker_postgres(project)
        if temp_storage is not None:
            shutil.rmtree(temp_storage)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote results to: {out_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", type=str, required=True)
    args = parser.parse_args()

    run_bench(args.repo_dir, args.output, args.label)
