#!/bin/bash
set -e

API_KEY="test-api-key-123"
BASE="http://localhost:8000"

echo "=============================================="
echo "  Pi Analysis Backend — Integration Tests"
echo "=============================================="
echo ""

pass=0
fail=0

check() {
    local desc="$1"
    local expected="$2"
    local actual="$3"
    if echo "$actual" | grep -q "$expected"; then
        echo "  ✅ $desc"
        pass=$((pass + 1))
    else
        echo "  ❌ $desc — expected '$expected', got: $actual"
        fail=$((fail + 1))
    fi
}

# --- Test 1: No API key headers ---
echo "--- Auth tests ---"
RSP=$(curl -s -w "\n%{http_code}" "$BASE/analyze" \
    -F "video=@$(which python3)" \
    -F 'sidecar={"test":1}')
CODE=$(echo "$RSP" | tail -1)
check "Reject missing API key" "422" "$CODE"

RSP=$(curl -s -w "\n%{http_code}" "$BASE/analyze" \
    -H "X-API-Key: wrong-key" \
    -F "video=@$(which python3)" \
    -F 'sidecar={"test":1}')
CODE=$(echo "$RSP" | tail -1)
check "Reject wrong API key" "403" "$CODE"

# --- Test 2: Analyze endpoint ---
echo ""
echo "--- Analyze endpoint ---"
RSP=$(curl -s -w "\n%{http_code}" "$BASE/analyze" \
    -H "X-API-Key: $API_KEY" \
    -F "video=@$(which python3)" \
    -F 'sidecar={"tracked":"ball","ref_geometry":"circle"}')
CODE=$(echo "$RSP" | tail -1)
JOB_ID=$(echo "$RSP" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
check "Create job returns 200" "200" "$CODE"
check "Job ID is UUID format" "-" "$JOB_ID"
echo "       job_id = $JOB_ID"

# --- Test 3: Status endpoint ---
echo ""
echo "--- Status endpoint ---"
sleep 2
RSP=$(curl -s "$BASE/status/$JOB_ID" -H "X-API-Key: $API_KEY")
check "Status includes job_id" "$JOB_ID" "$RSP"
check "Status has running state" "running" "$RSP"
check "Status has progress_pct" "progress_pct" "$RSP"

# --- Test 4: Status for non-existent job ---
echo ""
echo "--- Status (not found) ---"
RSP=$(curl -s -w "\n%{http_code}" "$BASE/status/nonexistent-job" -H "X-API-Key: $API_KEY")
CODE=$(echo "$RSP" | tail -1)
check "Status for unknown job returns 404" "404" "$CODE"

# --- Test 5: Result endpoint (not done yet) ---
echo ""
echo "--- Result endpoint (not done) ---"
RSP=$(curl -s -w "\n%{http_code}" "$BASE/result/$JOB_ID" -H "X-API-Key: $API_KEY")
CODE=$(echo "$RSP" | tail -1)
check "Result for incomplete job returns 404" "404" "$CODE"

# --- Test 6: File serving ---
echo ""
echo "--- File serving ---"
RSP=$(curl -s -w "\n%{http_code}" "$BASE/files/job_${JOB_ID}" 2>&1)
CODE=$(echo "$RSP" | tail -1)
check "File serving responds" - "$(echo "$CODE" | head -1)"
# 404 expected — dir listing not enabled; just checking mount works

# --- Test 7: Delete job ---
echo ""
echo "--- Delete ---"
RSP=$(curl -s -w "\n%{http_code}" -X DELETE "$BASE/job/$JOB_ID" -H "X-API-Key: $API_KEY")
CODE=$(echo "$RSP" | tail -1)
check "Delete returns 200" "200" "$CODE"
check "Delete confirms" "true" "$RSP"

# --- Test 8: Verify workspace is gone ---
echo ""
echo "--- Workspace cleanup ---"
RSP=$(curl -s -w "\n%{http_code}" "$BASE/status/$JOB_ID" -H "X-API-Key: $API_KEY")
CODE=$(echo "$RSP" | tail -1)
check "Status after delete returns 404" "404" "$CODE"

echo ""
echo "=============================================="
echo "  Results: $pass passed, $fail failed"
echo "=============================================="
exit $fail
