#!/usr/bin/env python3
"""Recompute samples. Exit 0 within limits, 1 review required, 2 invalid evidence."""
import argparse
import json
import math
from pathlib import Path
from benchmark_workloads import compute_stats


def validate_samples(samples, path):
    if not isinstance(samples, list) or not samples or any(
        isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0
        for x in samples
    ):
        raise ValueError(f"{path}: missing/invalid raw samples")


def measurements(node, path=""):
    if not isinstance(node, dict):
        return {}
    result = {}
    if "p95" in node or "raw_samples_ms" in node:
        samples = node.get("raw_samples_ms")
        validate_samples(samples, path)
        if node.get("count") != len(samples):
            raise ValueError(f"{path}: count mismatch")
        stats = compute_stats(samples)
        for metric in ("p50", "p95"):
            result[f"{path}.{metric}"] = stats[metric]
    for field, metric in (("raw_query_counts", "queries"), ("raw_peak_rss_mb", "peak_rss_mb")):
        if field in node:
            validate_samples(node[field], path)
            result[f"{path}.{metric}"] = max(node[field])
    if any(k.startswith("queries_per_") for k in node) and "raw_query_counts" not in node:
        raise ValueError(f"{path}: missing raw query counts")
    if "peak_rss_mb" in node and "raw_peak_rss_mb" not in node:
        raise ValueError(f"{path}: missing raw RSS samples")
    for key, value in node.items():
        if isinstance(value, dict):
            result.update(measurements(value, f"{path}.{key}" if path else key))
    return result


def compare(base, candidate, threshold=10.0):
    for run in (base, candidate):
        if not run.get("metadata", {}).get("tested_sha"):
            raise ValueError("missing tested_sha")
    if not base["metadata"].get("runner_sha256") or base["metadata"]["runner_sha256"] != candidate["metadata"].get("runner_sha256"):
        raise ValueError("different/missing workload runners")
    before, after = measurements(base["metrics"]), measurements(candidate["metrics"])
    if not before or before.keys() != after.keys():
        raise ValueError("workload mismatch")
    rows = []
    for key, old in before.items():
        new = after[key]
        delta = 100 * (new / old - 1) if old else (0 if new == 0 else None)
        gate = key.endswith((".p95", ".peak_rss_mb", ".queries"))
        regression = gate and new > old and (key.endswith(".queries") or delta is None or delta > threshold)
        rows.append({"metric": key, "baseline": old, "candidate": new, "delta_percent": delta,
                     "status": "REVIEW_REQUIRED" if regression else ("PASS" if gate else "INFO")})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        rows = compare(json.loads(args.baseline.read_text()), json.loads(args.candidate.read_text()))
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Invalid evidence: {exc}\n")
    report = {"status": "REVIEW_REQUIRED" if any(r["status"] == "REVIEW_REQUIRED" for r in rows) else "PASS", "rows": rows}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 1 if report["status"] == "REVIEW_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
