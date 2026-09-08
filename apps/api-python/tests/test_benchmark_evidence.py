import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from benchmark_workloads import compute_stats, percentile
from compare_benchmarks import compare


def run(samples):
    return {"metadata": {"tested_sha": "abc", "runner_sha256": "runner"}, "metrics": {"upload": compute_stats(samples)}}


def test_recomputes_raw_samples_instead_of_trusting_percentiles():
    base, candidate = run([10, 10, 10]), run([20, 20, 20])
    candidate["metrics"]["upload"]["p95"] = 1
    rows = compare(base, candidate)
    assert next(r for r in rows if r["metric"].endswith("p95"))["status"] == "REVIEW_REQUIRED"
    assert percentile([5], 95) == 5


def test_rejects_summary_only_evidence_and_missing_query_samples():
    base = run([10, 10])
    bad = copy.deepcopy(base)
    del bad["metrics"]["upload"]["raw_samples_ms"]
    with pytest.raises(ValueError, match="raw samples"):
        compare(base, bad)
    bad = copy.deepcopy(base)
    bad["metrics"]["queries_per_request"] = 4
    with pytest.raises(ValueError, match="raw query"):
        compare(base, bad)
