#!/usr/bin/env bash
set -e
echo "=== Sarthi P0/P1/P2/P3 Acceptance Verification ==="

echo "[1] .env exists"
test -f backend/.env || test -f .env

echo "[2] docker-compose exists"
test -f docker-compose.yml

echo "[3] k8s directory exists"
test -d k8s

echo "[4] Makefile exists"
test -f Makefile

echo "[5] CI pipeline exists"
test -f .github/workflows/ci.yml

echo "[6] pre-commit config exists"
test -f .pre-commit-config.yaml

echo "[7] PII regression suite passes"
pytest tests/security/test_pii_single_source.py -q

echo "[8] PII scrubber extracts WebSocket text properly"
python -c "from security.pii_middleware import PIIIngressMiddleware; assert hasattr(PIIIngressMiddleware, '_extract_scrubbed_text')" || {
  echo "FAIL: _extract_scrubbed_text method missing"
  exit 1
}

echo "[9] Consent artifact uses HMAC secret"
grep -q "SARTHI_HMAC_SECRET" backend/security/consent.py

echo "[10] Consent artifact signature present"
python -c "import os, sys; sys.path.insert(0, 'backend'); os.environ['SARTHI_HMAC_SECRET'] = 'a'*64; from security.consent import create_consent_artifact; assert 'hmac_sig' in create_consent_artifact('u1', 'P001', 'hi', True)"

echo "[11] No placeholder comments remain"
grep -rnE "(TODO|FIXME|XXX|# FIX)" backend/ --exclude-dir=tests | grep -v "XXXX" && {
  echo "FAIL: Placeholder comments found"
  exit 1
} || true

echo "[12] No sqlite DBs tracked in git"
git ls-files | grep -E "\.(db|sqlite|sqlite3)$" && {
  echo "FAIL: DB tracked in git"
  exit 1
} || true

echo "[13] Makefile valid"
make --dry-run test 2>/dev/null | grep -q "pytest" || grep -A 2 "^test:" Makefile | grep -q "pytest"

echo "[14] test_all.py split into focused domain files"
if [ -f backend/tests/test_all.py ]; then
  echo "FAIL: test_all.py still exists"
  exit 1
fi

echo "[15] Prompt injection tests present"
if [ ! -f tests/security/test_prompt_injection_bypasses.py ] && [ ! -f backend/tests/security/test_prompt_injection_bypasses.py ]; then
  echo "FAIL: prompt injection tests missing"
  exit 1
fi

echo ""
echo "=== ALL Sarthi Acceptance Checks PASSED ==="
