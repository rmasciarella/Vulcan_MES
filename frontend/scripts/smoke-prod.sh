#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${SITE_URL:-}" ]]; then
  echo "SITE_URL is required, e.g. SITE_URL=https://your-site.netlify.app bash scripts/smoke-prod.sh" >&2
  exit 1
fi

API_HEALTH_PATH="${API_HEALTH_PATH:-/api/health}"
HOME_STATUS=0
API_STATUS=0

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
ok() { printf "✅ %s\n" "$1"; }
warn() { printf "⚠️  %s\n" "$1"; }
fail() { printf "❌ %s\n" "$1"; }

bold "Checking home page SSR/SSG..."
HTML_HEAD=$(curl -sSL "$SITE_URL" | head -n 50)
if echo "$HTML_HEAD" | grep -qi "<!doctype html\|<html"; then
  ok "Home page returned HTML"
else
  warn "Home page did not return recognizable HTML in first 50 lines"
  HOME_STATUS=1
fi

bold "Checking API health endpoint (${API_HEALTH_PATH})..."
API_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SITE_URL$API_HEALTH_PATH" || true)
if [[ "$API_CODE" =~ ^2[0-9]{2}$ ]]; then
  ok "API health returned $API_CODE"
else
  warn "API health returned $API_CODE — adjust API_HEALTH_PATH or configure netlify.toml proxy"
  API_STATUS=1
fi

if [[ $HOME_STATUS -eq 0 && $API_STATUS -eq 0 ]]; then
  ok "Smoke tests passed"
  exit 0
else
  fail "Smoke tests had warnings/failures"
  exit 1
fi

