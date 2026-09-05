# Cleanup timeout and benchmark correction — verification

Status: implementation verified locally; performance comparison requires review. No production or clean-commit acceptance is asserted.

## Implemented behavior

- Media coordinator no longer writes private `_rolled_back` flags. Successful rollback alone establishes rollback-confirmed.
- UoW port explicitly owns the cleanup task. Timeout requests cancellation but does not assume completion. The persistence adapter retains the task/scope until settlement finishes, then closes the session. Rollback and close cannot overlap on this path.
- Pending scopes are strongly referenced and observed; admission of new UoW transactions on the same event loop is suspended while a quarantined scope remains. This is a deliberate availability tradeoff during an exceptional failure, not normal request behavior.
- Shutdown drains quarantined tasks for five seconds. If still pending, it logs and raises rather than disposing engine/storage concurrently with a live task. An indefinitely noncooperative task requires process-level termination/recovery; the implementation does not pretend it can forcibly stop arbitrary Python I/O safely.
- Cleanup/close failure is logged without replacing the original request error. Regression tests include cancel-resistant rollback, actual PostgreSQL pool checkout/release, admission suspension, shutdown timeout, failed rollback and failed close.

## Benchmark corrections

- Runner uses its own isolated PostgreSQL test project, validates QA/publish status and exact catalog fixture cardinality, discards five warmup iterations, and records raw latencies/query counts/RSS samples.
- Percentile interpolation handles integer positions/singleton samples correctly.
- Evidence records runner hash, tested HEAD, source hash and dirty paths. Candidate here is a working-tree measurement, not a clean committed artifact.
- Comparator recalculates p50/p95 from samples, rejects summary-only or incompatible evidence, and exits 1 with REVIEW_REQUIRED for threshold violations. It never auto-approves a tradeoff.

New evidence: [baseline](evidence/cleanup-fix/baseline.json), [candidate-final](evidence/cleanup-fix/candidate-final.json), [computed comparison](evidence/cleanup-fix/comparison-final.json).

Measured sequential runs, baseline `2f5e200` versus working tree based on `7053273` (candidate-final was run before this commit, with source status recorded in its metadata):

| Metric | Baseline | Candidate | Interpretation |
|---|---:|---:|---|
| Login p95 | 30.691 ms | 31.371 ms | +2.2%, within 10% |
| Upload p95 | 22.529 ms | 26.875 ms | REVIEW_REQUIRED, +19.3% |
| Upload query count | 4 | 5 | REVIEW_REQUIRED; write-scope catalog recheck |
| Progress-request p95 | 7.960 ms | 13.381 ms | REVIEW_REQUIRED |
| Session lifecycle p95 | 21.014 ms | 24.483 ms | REVIEW_REQUIRED |
| Peak RSS | 220.55 MB | 244.83 MB | REVIEW_REQUIRED, +11.0% |

These are local samples, not a soak test. Other flagged rows are listed in the computed comparison. Existing historical CTO approval is not reused for new results. The comparator returns `REVIEW_REQUIRED`; performance acceptance remains open until the flagged query/latency/memory changes are investigated or explicitly reviewed against a measured budget.

## Commands and checks

- `pnpm test:guard`: PASS.
- `PYTHONPATH=apps/api-python/src apps/api-python/.venv/bin/python -m jplearn_api.openapi_diff`: PASS.
- `uv run pytest -q`: 202 PASS, 2 deprecation warnings, 24.97 seconds.
- Media/architecture targeted regression suite: 54 PASS; new cleanup/benchmark tests also PASS, including a real PostgreSQL connection lifecycle case.
- Web E2E Chromium + WebKit: 10 PASS, 2.2 minutes. Ephemeral run evidence: `/tmp/jplearn-e2e-20260905221443_18702`.
- Container final rebuild: 7/7 PASS, UID 10001, packaged resources, migration/adoption and readiness isolation. Image `sha256:b45c05fa1f1ce94600036b83b33ab92365353a16b33ebde82346b45087ff59f7`. Manifest: `/tmp/jplearn-fix-evidence.hpkdqP/container-final.json`, explicitly reports DIRTY source. This verifies the local artifact; it is not clean-source provenance.

Reproduce measurements in separate processes using the same current runner:

```bash
apps/api-python/.venv/bin/python scripts/benchmark_workloads.py --repo-dir /path/to/baseline-checkout --label baseline --output /tmp/baseline.json
apps/api-python/.venv/bin/python scripts/benchmark_workloads.py --repo-dir /path/to/candidate-checkout --label candidate --output /tmp/candidate.json
apps/api-python/.venv/bin/python scripts/compare_benchmarks.py --baseline /tmp/baseline.json --candidate /tmp/candidate.json --output /tmp/comparison.json
```

No user changes to `walkthrough.md` or `landing_preview.html` were modified by this fix. Development database/media volumes were not used for testing. R-09 remains HOLD.
