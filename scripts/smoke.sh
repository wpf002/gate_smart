#!/usr/bin/env bash
# Pre-demo smoke test — hits every endpoint the UI loads on first paint.
# Exits 0 if all green, 1 if anything regressed.
#
#   ./scripts/smoke.sh
#
set -u

FRONTEND="https://gate-smart.up.railway.app"
BACKEND="https://backend-production-15e941.up.railway.app"
TOMORROW=$(date -v+1d +%Y-%m-%d 2>/dev/null || date -d "+1 day" +%Y-%m-%d)

checks=(
  "Backend health|${BACKEND}/health|200"
  "Frontend shell|${FRONTEND}/|200"
  "Races today (via nginx proxy)|${FRONTEND}/api/races/today|200"
  "Races tomorrow (via nginx proxy)|${FRONTEND}/api/races/date/${TOMORROW}|200"
)

fail=0
printf "%-42s %-8s %-8s %s\n" "Check" "Status" "Time" "URL"
printf -- "----------------------------------------------------------------------------------------------------------\n"
for row in "${checks[@]}"; do
  IFS='|' read -r label url expected <<< "$row"
  out=$(curl -sS -o /dev/null -w "%{http_code} %{time_total}" --max-time 30 "$url" 2>&1) || out="000 0"
  code=$(echo "$out" | awk '{print $1}')
  time=$(echo "$out" | awk '{print $2}')
  if [ "$code" = "$expected" ]; then
    mark="PASS"
  else
    mark="FAIL"
    fail=$((fail+1))
  fi
  printf "%-42s %-8s %-8s %s\n" "$label" "$code $mark" "${time}s" "$url"
done

echo
if [ $fail -eq 0 ]; then
  echo "All green — safe to demo."
  exit 0
else
  echo "$fail check(s) failed — DO NOT start the demo."
  exit 1
fi
