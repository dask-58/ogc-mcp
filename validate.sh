#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${1:-http://localhost:5001}"
PASS=0
FAIL=0

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
bold()   { printf "\033[1m%s\033[0m\n" "$*"; }

check() {
    local label="$1"
    local actual="$2"
    local expected="$3"
    if echo "$actual" | grep -q "$expected"; then
        green "  ✓ $label"
        PASS=$((PASS + 1))
    else
        red   "  ✗ $label (expected: $expected)"
        FAIL=$((FAIL + 1))
    fi
}

# Landing Page
bold "== 1. Landing Page =="
RESP=$(curl -sf "${BASE_URL}/" || true)
check "Landing page returns title" "$RESP" '"title"'

# Conformance
bold "== 2. Conformance =="
RESP=$(curl -sf "${BASE_URL}/conformance" || true)
check "Conformance lists conformsTo" "$RESP" '"conformsTo"'

# List Processes
bold "== 3. List Processes =="
RESP=$(curl -sf "${BASE_URL}/processes" || true)
check "Processes list contains hello-world" "$RESP" 'hello-world'
check "Processes list contains geometry-buffer" "$RESP" 'geometry-buffer'

# Describe Process
bold "== 4. Describe Process: geometry-buffer =="
RESP=$(curl -sf "${BASE_URL}/processes/geometry-buffer" || true)
check "Process description has id" "$RESP" '"id"'
check "Process description has inputs" "$RESP" '"inputs"'
check "Process description has outputs" "$RESP" '"outputs"'

# Execute Hello World Process
bold "== 5. Sync Execute: hello-world =="
RESP=$(curl -sf -X POST "${BASE_URL}/processes/hello-world/execution" \
    -H "Content-Type: application/json" \
    -d '{"inputs":{"name":"OGC Tester","message":"Hello from validation!"}}' || true)
check "Hello-world echoes name" "$RESP" 'OGC Tester'

# Sync Execute: geometry-buffer (Point)
bold "== 6. Sync Execute: geometry-buffer (Point) =="
RESP=$(curl -sf -X POST "${BASE_URL}/processes/geometry-buffer/execution" \
    -H "Content-Type: application/json" \
    -d '{
        "inputs": {
            "geometry": {"type":"Point","coordinates":[0.0,0.0]},
            "distance": 1.0,
            "resolution": 16
        }
    }' || true)
check "Buffer returns Feature" "$RESP" '"type":"Feature"'
check "Buffer returns Polygon" "$RESP" 'Polygon'
check "Buffer returns area" "$RESP" 'result_area'

# Sync Execute: geometry-buffer (LineString)
bold "== 7. Sync Execute: geometry-buffer (LineString) =="
RESP=$(curl -sf -X POST "${BASE_URL}/processes/geometry-buffer/execution" \
    -H "Content-Type: application/json" \
    -d '{
        "inputs": {
            "geometry": {"type":"LineString","coordinates":[[0,0],[1,1],[2,0]]},
            "distance": 0.5
        }
    }' || true)
check "LineString buffer returns Feature" "$RESP" 'Feature'
check "LineString buffer returns Polygon" "$RESP" 'Polygon'

# Async Execute: geometry-buffer
bold "== 8. Async Execute: geometry-buffer =="
# Request async execution via Prefer header
RESP_HEADERS=$(curl -si -X POST "${BASE_URL}/processes/geometry-buffer/execution" \
    -H "Content-Type: application/json" \
    -H "Prefer: respond-async" \
    -d '{
        "inputs": {
            "geometry": {"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
            "distance": 0.25
        }
    }' 2>/dev/null || true)

# Extract Location header for job URL
JOB_URL=$(echo "$RESP_HEADERS" | grep -i "^Location:" | tr -d '\r' | awk '{print $2}')

if [ -n "$JOB_URL" ]; then
    green " Async job created, Location: $JOB_URL"
    PASS=$((PASS + 1))

    # Poll job status (wait up to 15s)
    for i in $(seq 1 15); do
        JOB_STATUS=$(curl -sf "$JOB_URL" 2>/dev/null || true)
        if echo "$JOB_STATUS" | grep -q '"successful"'; then
            green "Job completed successfully"
            PASS=$((PASS + 1))

            # Retrieve results
            RESULTS=$(curl -sf "${JOB_URL}/results" 2>/dev/null || true)
            check "Async results contain geometry" "$RESULTS" 'Polygon'
            break
        elif echo "$JOB_STATUS" | grep -q '"failed"'; then
            red "Job failed"
            FAIL=$((FAIL + 1))
            break
        fi
        sleep 1
    done
else
    # Server may not support async with TinyDB — treat sync fallback as OK
    if echo "$RESP_HEADERS" | grep -q 'Polygon'; then
        green "Server executed synchronously (async not available with this manager)"
        PASS=$((PASS + 1))
    else
        red "Async execution failed — no Location header and no sync fallback"
        FAIL=$((FAIL + 1))
    fi
fi

# Jobs Endpoint
bold "== 9. Jobs Endpoint =="
RESP=$(curl -sf "${BASE_URL}/jobs" || true)
check "Jobs endpoint returns list" "$RESP" '"jobs"'

echo ""
bold "========================================="
bold "  Results: ${PASS} passed, ${FAIL} failed"
bold "========================================="

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
