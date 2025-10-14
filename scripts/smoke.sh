#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8000}
FAIL=0

log(){ echo "[smoke] $*"; }
check(){ local name=$1; shift; if "$@" > /dev/null 2>&1; then log "OK  - $name"; else log "FAIL- $name"; FAIL=1; fi }

log "Smoke test contra ${BASE_URL}"

# /health
check health curl -fsS "${BASE_URL}/health"

# /ready (puede tardar breve tiempo; reintentos)
for i in {1..5}; do
  if curl -fsS "${BASE_URL}/ready" | grep -q '"status": "ready"'; then
    log "OK  - ready"
    break
  else
    log "Esperando readiness (intento $i)"; sleep 1
  fi
  if [[ $i -eq 5 ]]; then log "FAIL- ready"; FAIL=1; fi
done

# /classify
check classify curl -fsS -X POST "${BASE_URL}/classify" -H 'Content-Type: application/json' -d '{"query":"iphone 13 128gb","lang":"es","top_k":3}'

# /taxonomy/search
check taxo_search curl -fsS "${BASE_URL}/taxonomy/search?q=chocolate&lang=es&limit=3"

# /taxonomy/autocomplete
check taxo_auto curl -fsS "${BASE_URL}/taxonomy/autocomplete?q=choc&lang=es&limit=3"

# /metrics (puede estar protegido por ENABLE_METRICS=0 si se desactiva)
if curl -fsS "${BASE_URL}/metrics" | grep -q twic_requests_total; then
  log "OK  - metrics"
else
  log "WARN- metrics endpoint no accesible o sin métrica twic_requests_total"
fi

if [[ $FAIL -eq 0 ]]; then
  log "SMOKE PASSED"
  exit 0
else
  log "SMOKE FAILED"
  exit 1
fi
