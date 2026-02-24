#!/usr/bin/env python3
"""
Usage:
    python validate_tests.py [BASE_URL]

Default BASE_URL: http://localhost:5001
"""

import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL: str = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5001"
ASYNC_POLL_INTERVAL_S: float = 1.0
ASYNC_POLL_TIMEOUT_S: float = 30.0

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"


def green(s: str) -> None:
    print(f"{GREEN}{s}{RESET}")


def red(s: str) -> None:
    print(f"{RED}{s}{RESET}")


def yellow(s: str) -> None:
    print(f"{YELLOW}{s}{RESET}")


def bold(s: str) -> None:
    print(f"{BOLD}{s}{RESET}")


# ---------------------------------------------------------------------------
# Results tracker
# ---------------------------------------------------------------------------
@dataclass
class Results:
    passed: int = 0
    failed: int = 0
    latencies_ms: Dict[str, List[float]] = field(default_factory=dict)

    def check(self, label: str, condition: bool, detail: str = "") -> None:
        if condition:
            green(f"  ✓ {label}")
            self.passed += 1
        else:
            red(f"  ✗ {label}" + (f" — {detail}" if detail else ""))
            self.failed += 1

    def record_latency(self, name: str, ms: float) -> None:
        self.latencies_ms.setdefault(name, []).append(ms)

    def summary(self) -> None:
        print()
        bold("=" * 48)
        bold(f"  Results: {self.passed} passed, {self.failed} failed")
        bold("=" * 48)

    def metrics(self) -> None:
        if not self.latencies_ms:
            return
        print()
        bold("── Performance Metrics ──────────────────────────")
        for name, values in self.latencies_ms.items():
            mn = min(values)
            mx = max(values)
            avg = statistics.mean(values)
            p50 = statistics.median(values)
            print(
                f"  {name:35s}  "
                f"min={mn:.0f}ms  p50={p50:.0f}ms  avg={avg:.0f}ms  max={mx:.0f}ms"
            )
        bold("─" * 48)


results = Results()


# ---------------------------------------------------------------------------
# HTTP helpers (synchronous with timing)
# ---------------------------------------------------------------------------
def get(path: str, headers: Optional[Dict] = None) -> Tuple[httpx.Response, float]:
    url = BASE_URL.rstrip("/") + path
    t0 = time.monotonic()
    try:
        r = httpx.get(url, headers=headers or {}, timeout=10.0)
    except httpx.RequestError as exc:
        raise SystemExit(f"[FATAL] GET {url} failed: {exc}")
    ms = (time.monotonic() - t0) * 1000
    return r, ms


def post(
    path: str,
    payload: Any,
    headers: Optional[Dict] = None,
) -> Tuple[httpx.Response, float]:
    url = BASE_URL.rstrip("/") + path
    h = {"Content-Type": "application/json", **(headers or {})}
    t0 = time.monotonic()
    try:
        r = httpx.post(url, content=json.dumps(payload), headers=h, timeout=10.0)
    except httpx.RequestError as exc:
        raise SystemExit(f"[FATAL] POST {url} failed: {exc}")
    ms = (time.monotonic() - t0) * 1000
    return r, ms


def post_raw(
    path: str,
    body: bytes,
    headers: Optional[Dict] = None,
) -> Tuple[httpx.Response, float]:
    """POST with arbitrary body (used to test malformed JSON)."""
    url = BASE_URL.rstrip("/") + path
    h = {"Content-Type": "application/json", **(headers or {})}
    t0 = time.monotonic()
    try:
        r = httpx.post(url, content=body, headers=h, timeout=10.0)
    except httpx.RequestError as exc:
        raise SystemExit(f"[FATAL] POST {url} failed: {exc}")
    ms = (time.monotonic() - t0) * 1000
    return r, ms


# ---------------------------------------------------------------------------
# Async helper: poll a job URL until success / failure / timeout
# ---------------------------------------------------------------------------
async def poll_async_job(job_url: str) -> Optional[Dict]:
    """Poll a job status URL until the job is successful or failed."""
    deadline = time.monotonic() + ASYNC_POLL_TIMEOUT_S
    async with httpx.AsyncClient(timeout=10.0) as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(job_url)
                if r.status_code == 200:
                    data = r.json()
                    status = data.get("status", "")
                    if status == "successful":
                        return data
                    if status == "failed":
                        return data
                    # Still running — print progress
                    yellow(f"    … job status: {status}")
            except httpx.RequestError:
                pass
            await asyncio.sleep(ASYNC_POLL_INTERVAL_S)
    return None  # timed out


# ---------------------------------------------------------------------------
# Test sections
# ---------------------------------------------------------------------------


def test_landing_page() -> None:
    bold("\n== 1. Landing Page ==")
    r, ms = get("/")
    results.record_latency("GET /", ms)
    results.check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    try:
        body = r.json()
        results.check("Response has 'title' field", "title" in body)
        results.check("Response has 'links' field", "links" in body)
    except Exception:
        results.check("Response is valid JSON", False)


def test_conformance() -> None:
    bold("\n== 2. Conformance ==")
    r, ms = get("/conformance")
    results.record_latency("GET /conformance", ms)
    results.check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    try:
        body = r.json()
        results.check("Has 'conformsTo' list", isinstance(body.get("conformsTo"), list))
    except Exception:
        results.check("Response is valid JSON", False)


def test_list_processes() -> None:
    bold("\n== 3. List Processes ==")
    r, ms = get("/processes")
    results.record_latency("GET /processes", ms)
    results.check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    try:
        body = r.json()
        ids = [p.get("id") for p in body.get("processes", [])]
        results.check("'hello-world' listed", "hello-world" in ids)
        results.check("'geometry-buffer' listed", "geometry-buffer" in ids)
    except Exception:
        results.check("Response is valid JSON", False)


def test_describe_process() -> None:
    bold("\n== 4. Describe Process: geometry-buffer ==")
    r, ms = get("/processes/geometry-buffer")
    results.record_latency("GET /processes/geometry-buffer", ms)
    results.check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    try:
        body = r.json()
        results.check("Has 'id'", "id" in body)
        results.check("Has 'inputs'", "inputs" in body)
        results.check("Has 'outputs'", "outputs" in body)
        results.check(
            "Supports async-execute job control",
            "async-execute" in body.get("jobControlOptions", []),
        )
    except Exception:
        results.check("Response is valid JSON", False)


def test_sync_hello_world() -> None:
    bold("\n== 5. Sync Execute: hello-world ==")
    payload = {"inputs": {"name": "OGC Tester", "message": "Hello from validation!"}}
    r, ms = post("/processes/hello-world/execution", payload)
    results.record_latency("POST /processes/hello-world/execution (sync)", ms)
    results.check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    try:
        body = r.json()
        text = json.dumps(body)
        results.check("Response echoes 'OGC Tester'", "OGC Tester" in text)
    except Exception:
        results.check("Response is valid JSON", False)


def test_sync_geometry_buffer_point() -> None:
    bold("\n== 6. Sync Execute: geometry-buffer (Point) ==")
    payload = {
        "inputs": {
            "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            "distance": 1.0,
            "resolution": 16,
        }
    }
    r, ms = post("/processes/geometry-buffer/execution", payload)
    results.record_latency("POST /processes/geometry-buffer/execution (Point)", ms)
    results.check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    try:
        body = r.json()
        results.check("Response type is 'Feature'", body.get("type") == "Feature")
        results.check(
            "Geometry is Polygon",
            body.get("geometry", {}).get("type") == "Polygon",
        )
        props = body.get("properties", {})
        results.check("'result_area' in properties", "result_area" in props)
        results.check("'buffer_distance' in properties", "buffer_distance" in props)
        results.check(
            "Area > 0",
            isinstance(props.get("result_area"), (int, float))
            and props["result_area"] > 0,
        )
    except Exception as exc:
        results.check("Response is valid JSON", False, str(exc))


def test_sync_geometry_buffer_linestring() -> None:
    bold("\n== 7. Sync Execute: geometry-buffer (LineString) ==")
    payload = {
        "inputs": {
            "geometry": {
                "type": "LineString",
                "coordinates": [[0, 0], [1, 1], [2, 0]],
            },
            "distance": 0.5,
        }
    }
    r, ms = post("/processes/geometry-buffer/execution", payload)
    results.record_latency("POST /processes/geometry-buffer/execution (LineString)", ms)
    results.check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    try:
        body = r.json()
        results.check("Response type is 'Feature'", body.get("type") == "Feature")
        results.check(
            "Geometry is Polygon",
            body.get("geometry", {}).get("type") == "Polygon",
        )
    except Exception as exc:
        results.check("Response is valid JSON", False, str(exc))


def test_error_handling() -> None:
    bold("\n== 8. Error Handling ==")

    # Missing required input
    r, ms = post("/processes/geometry-buffer/execution", {"inputs": {"distance": 1.0}})
    results.check(
        "Missing 'geometry' input → 4xx or error body",
        r.status_code >= 400
        or "error" in r.text.lower()
        or "missing" in r.text.lower(),
        f"status={r.status_code}",
    )

    # Malformed JSON
    r, ms = post_raw(
        "/processes/hello-world/execution",
        b'{"inputs": {"name": "Bad"',  # intentionally truncated
    )
    results.check(
        "Malformed JSON body → 4xx",
        r.status_code >= 400,
        f"status={r.status_code}",
    )

    # Unknown process
    r, ms = get("/processes/does-not-exist")
    results.check(
        "Unknown process → 404",
        r.status_code == 404,
        f"got {r.status_code}",
    )


def test_async_execute() -> None:
    bold("\n== 9. Async Execute: geometry-buffer (Polygon) ==")
    payload = {
        "inputs": {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
            "distance": 0.25,
        }
    }
    r, ms = post(
        "/processes/geometry-buffer/execution",
        payload,
        headers={"Prefer": "respond-async"},
    )
    results.record_latency("POST /processes/geometry-buffer/execution (async)", ms)

    location = r.headers.get("Location", "")

    if r.status_code == 201 and location:
        green(f"  Async job accepted → Location: {location}")
        results.check("HTTP 201 (Created)", r.status_code == 201)

        # Build absolute job URL
        job_url = (
            location if location.startswith("http") else BASE_URL.rstrip("/") + location
        )

        t_poll_start = time.monotonic()
        job_data = asyncio.run(poll_async_job(job_url))
        poll_elapsed_ms = (time.monotonic() - t_poll_start) * 1000
        results.record_latency("Async job polling", poll_elapsed_ms)

        if job_data is None:
            red(f"  Async job timed out after {ASYNC_POLL_TIMEOUT_S:.0f}s")
            results.failed += 1
        else:
            status = job_data.get("status", "")
            results.check(
                "Job status is 'successful'", status == "successful", f"got '{status}'"
            )

            if status == "successful":
                # Fetch results — job_url is already absolute, don't go through get()
                # Use ?f=json + Accept header so pygeoapi returns JSON, not HTML
                results_url = job_url.rstrip("/") + "/results?f=json"
                t0 = time.monotonic()
                try:
                    result_r = httpx.get(
                        results_url,
                        headers={"Accept": "application/json"},
                        timeout=10.0,
                    )
                except httpx.RequestError as exc:
                    red(f"  Could not fetch results: {exc}")
                    results.failed += 1
                    return
                result_ms = (time.monotonic() - t0) * 1000
                results.record_latency("GET job results", result_ms)
                results.check(
                    "Results endpoint returns 200",
                    result_r.status_code == 200,
                    f"got {result_r.status_code}",
                )
                # The result may be the Feature directly or wrapped under a key
                raw = result_r.text
                results.check(
                    "Results contain geometry output",
                    "Polygon" in raw or "buffered_geometry" in raw or "Feature" in raw,
                    f"body: {raw[:120]}",
                )

    elif r.status_code == 200:
        # Server executed synchronously instead of asynchronously
        yellow("  Server fell back to sync execution (no Location header)")
        try:
            body = r.json()
            results.check(
                "Sync fallback returns Feature",
                body.get("type") == "Feature",
            )
        except Exception:
            results.check("Sync fallback returns JSON", False)
    else:
        results.check(
            "Async accepted (201) or sync fallback (200)",
            False,
            f"status={r.status_code}, location='{location}'",
        )


def test_jobs_endpoint() -> None:
    bold("\n== 10. Jobs Endpoint ==")
    r, ms = get("/jobs")
    results.record_latency("GET /jobs", ms)
    results.check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    try:
        body = r.json()
        jobs = body.get("jobs", [])
        results.check("Response has 'jobs' list", isinstance(jobs, list))
        if jobs:
            first = jobs[0]
            results.check("First job has 'jobID'", "jobID" in first)
            results.check("First job has 'status'", "status" in first)
    except Exception as exc:
        results.check("Response is valid JSON", False, str(exc))


def test_response_times() -> None:
    """Quick latency benchmark: repeat each light endpoint 5 times."""
    bold("\n== 11. Repeated Latency Benchmark (n=5) ==")
    ENDPOINTS = ["/", "/conformance", "/processes"]
    for ep in ENDPOINTS:
        for _ in range(5):
            _, ms = get(ep)
            results.record_latency(f"GET {ep}", ms)
    green("  Benchmark done — see metrics below.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    bold(f"\n{'=' * 48}")
    bold(f"  OGC API – Processes Validation Suite")
    bold(f"  Target: {BASE_URL}")
    bold(f"{'=' * 48}")

    test_landing_page()
    test_conformance()
    test_list_processes()
    test_describe_process()
    test_sync_hello_world()
    test_sync_geometry_buffer_point()
    test_sync_geometry_buffer_linestring()
    test_error_handling()
    test_async_execute()
    test_jobs_endpoint()
    test_response_times()

    results.summary()
    results.metrics()

    sys.exit(0 if results.failed == 0 else 1)


if __name__ == "__main__":
    main()
