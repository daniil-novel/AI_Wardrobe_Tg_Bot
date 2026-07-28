"""Reproducible in-process latency smoke benchmark for public API routes."""

from __future__ import annotations

import argparse
import json
import logging
import time
import tracemalloc
from collections.abc import Sequence

from aiwardrobe_api.main import create_app
from fastapi.testclient import TestClient


def percentile(sorted_values: Sequence[float], quantile: float) -> float:
    if not sorted_values:
        raise ValueError("At least one value is required.")
    position = (len(sorted_values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def benchmark(client: TestClient, path: str, iterations: int) -> dict[str, float | int | str]:
    for _ in range(20):
        response = client.get(path)
        response.raise_for_status()

    timings_ms: list[float] = []
    tracemalloc.start()
    started = time.perf_counter()
    for _ in range(iterations):
        request_started = time.perf_counter_ns()
        response = client.get(path)
        response.raise_for_status()
        timings_ms.append((time.perf_counter_ns() - request_started) / 1_000_000)
    elapsed = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    ordered = sorted(timings_ms)
    return {
        "path": path,
        "iterations": iterations,
        "requests_per_second": round(iterations / elapsed, 2),
        "latency_p50_ms": round(percentile(ordered, 0.50), 3),
        "latency_p95_ms": round(percentile(ordered, 0.95), 3),
        "latency_p99_ms": round(percentile(ordered, 0.99), 3),
        "latency_max_ms": round(max(ordered), 3),
        "tracemalloc_peak_mib": round(peak_bytes / 1024 / 1024, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=500)
    args = parser.parse_args()
    if args.iterations < 20:
        parser.error("--iterations must be at least 20")

    with TestClient(create_app()) as client:
        logging.disable(logging.CRITICAL)
        try:
            results = [
                benchmark(client, "/", args.iterations),
                benchmark(client, "/billing/plans", args.iterations),
            ]
        finally:
            logging.disable(logging.NOTSET)
    print(json.dumps({"mode": "in_process_testclient", "results": results}, indent=2))


if __name__ == "__main__":
    main()
