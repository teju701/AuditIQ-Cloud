from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


DEFAULT_QUERIES = [
    "Show vendors who share the same GSTIN",
    "Show monthly trend of invoice count over time",
    "Give me a breakdown of transactions by department",
]


def _request(method: str, url: str, body: bytes | None, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def _post_json(base_url: str, path: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, str], dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    status, headers, raw = _request(
        method="POST",
        url=f"{base_url}{path}",
        body=body,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except json.JSONDecodeError:
        parsed = {"raw": raw.decode("utf-8", errors="replace")}
    return status, headers, parsed


def _multipart_upload(base_url: str, dataset_path: Path, timeout: float) -> dict[str, Any]:
    file_bytes = dataset_path.read_bytes()
    boundary = f"----AuditIQBoundary{uuid.uuid4().hex}"
    filename = dataset_path.name

    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        b'Content-Disposition: form-data; name="file"; filename="' + filename.encode("utf-8") + b'"\r\n',
        b"Content-Type: text/csv\r\n\r\n",
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    body = b"".join(parts)

    status, _, raw = _request(
        method="POST",
        url=f"{base_url}/upload",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=timeout,
    )

    if status != 200:
        raise RuntimeError(f"Upload failed with status {status}: {raw.decode('utf-8', errors='replace')}")

    return json.loads(raw.decode("utf-8"))


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    idx = (len(ordered) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def _time_query(base_url: str, dataset_id: str, query: str, timeout: float) -> tuple[float, dict[str, Any]]:
    start = time.perf_counter()
    status, _, payload = _post_json(
        base_url,
        "/query",
        {"dataset_id": dataset_id, "query": query},
        timeout,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    if status != 200:
        raise RuntimeError(f"Query failed ({status}) for '{query}': {payload}")

    return elapsed_ms, payload


def _run_mode(
    base_url: str,
    dataset_id: str,
    query: str,
    iterations: int,
    timeout: float,
    invalidate_before_each: bool,
) -> dict[str, Any]:
    latencies: list[float] = []
    cache_hits: list[bool] = []
    execution_modes: set[str] = set()

    for _ in range(iterations):
        if invalidate_before_each:
            _post_json(base_url, "/cache/invalidate", {}, timeout)

        elapsed_ms, payload = _time_query(base_url, dataset_id, query, timeout)
        latencies.append(elapsed_ms)
        cache_hits.append(bool(payload.get("cache", {}).get("hit")))
        execution_modes.add(str(payload.get("execution_mode")))

    return {
        "count": len(latencies),
        "avg_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "p50_ms": round(_percentile(latencies, 0.50), 2),
        "p95_ms": round(_percentile(latencies, 0.95), 2),
        "min_ms": round(min(latencies), 2) if latencies else 0.0,
        "max_ms": round(max(latencies), 2) if latencies else 0.0,
        "cache_hit_rate": round((sum(1 for hit in cache_hits if hit) / len(cache_hits)) * 100.0, 2) if cache_hits else 0.0,
        "execution_modes": sorted(execution_modes),
    }


def benchmark(base_url: str, dataset_path: Path, iterations: int, timeout: float, queries: list[str]) -> dict[str, Any]:
    health_status, _, health_payload = _post_json(base_url, "/cache/invalidate", {}, timeout)
    if health_status != 200:
        raise RuntimeError(f"Cannot reach backend cache endpoint at {base_url}/cache/invalidate")

    upload_payload = _multipart_upload(base_url, dataset_path, timeout)
    dataset_id = upload_payload["dataset_id"]

    report: dict[str, Any] = {
        "base_url": base_url,
        "dataset_path": str(dataset_path),
        "dataset_id": dataset_id,
        "dataset_hash": upload_payload.get("dataset_hash"),
        "iterations": iterations,
        "queries": [],
    }

    for query in queries:
        # Cold path: force cache miss each run.
        cold = _run_mode(base_url, dataset_id, query, iterations, timeout, invalidate_before_each=True)

        # Warm path: prime once, then repeated query to observe cache hits.
        _post_json(base_url, "/cache/invalidate", {}, timeout)
        _time_query(base_url, dataset_id, query, timeout)
        warm = _run_mode(base_url, dataset_id, query, iterations, timeout, invalidate_before_each=False)

        report["queries"].append(
            {
                "query": query,
                "cold_cache": cold,
                "warm_cache": warm,
                "speedup_x_p50": round((cold["p50_ms"] / warm["p50_ms"]), 2) if warm["p50_ms"] > 0 else None,
                "speedup_x_p95": round((cold["p95_ms"] / warm["p95_ms"]), 2) if warm["p95_ms"] > 0 else None,
            }
        )

    return report


def _print_report(report: dict[str, Any]) -> None:
    print("=" * 90)
    print("AuditIQ Query Benchmark")
    print("=" * 90)
    print(f"Base URL   : {report['base_url']}")
    print(f"Dataset ID : {report['dataset_id']}")
    print(f"Iterations : {report['iterations']}")
    print("-" * 90)

    for item in report["queries"]:
        print(f"Query: {item['query']}")
        cold = item["cold_cache"]
        warm = item["warm_cache"]

        print(
            f"  Cold  -> p50={cold['p50_ms']} ms, p95={cold['p95_ms']} ms, "
            f"avg={cold['avg_ms']} ms, cache_hit_rate={cold['cache_hit_rate']}%, modes={cold['execution_modes']}"
        )
        print(
            f"  Warm  -> p50={warm['p50_ms']} ms, p95={warm['p95_ms']} ms, "
            f"avg={warm['avg_ms']} ms, cache_hit_rate={warm['cache_hit_rate']}%, modes={warm['execution_modes']}"
        )
        print(
            f"  Speedup -> p50 x{item['speedup_x_p50']}, p95 x{item['speedup_x_p95']}"
        )
        print("-" * 90)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark AuditIQ query latency with and without cache")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument(
        "--dataset",
        default=str((Path(__file__).resolve().parent.parent / "data" / "transactions.csv")),
        help="Path to CSV dataset file",
    )
    parser.add_argument("--iterations", type=int, default=8, help="Iterations per query per mode")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--queries",
        nargs="*",
        default=None,
        help="Optional list of queries. If omitted, built-in representative queries are used.",
    )
    parser.add_argument("--output-json", default="", help="Optional output path to persist benchmark JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    dataset_path = Path(args.dataset).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    queries = args.queries if args.queries else DEFAULT_QUERIES
    report = benchmark(args.base_url.rstrip("/"), dataset_path, max(1, args.iterations), args.timeout, queries)

    _print_report(report)

    if args.output_json:
        output_path = Path(args.output_json).resolve()
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved benchmark report to: {output_path}")


if __name__ == "__main__":
    main()
