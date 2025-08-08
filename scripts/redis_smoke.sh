#!/usr/bin/env sh
# Simple Redis smoke test: SET/GET a key via REDIS_URL
set -eu
: "${REDIS_URL:=redis://redis:6379}"

printf "PING -> %s\n" "$(redis-cli -u "$REDIS_URL" ping)"
redis-cli -u "$REDIS_URL" set smoke:ts "$(date +%s)" >/dev/null
val="$(redis-cli -u "$REDIS_URL" get smoke:ts)"
printf "GET smoke:ts -> %s\n" "$val"
[ -n "$val" ] && echo "OK: Redis reachable" || { echo "FAIL: Redis get returned empty"; exit 1; }

