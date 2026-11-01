#!/bin/sh
set -u
set -o pipefail

KEEP=14
AT=$((3 * 3600 + 30 * 60))

dump() {
  f="/backups/coffee-$(date +%Y-%m-%d_%H%M).sql.gz"
  if pg_dump -h db -U coffee -d coffee --clean --if-exists --no-owner --no-privileges | gzip -9 > "$f.part"; then
    mv "$f.part" "$f"
    ls -1t /backups/coffee-*.sql.gz | tail -n +$((KEEP + 1)) | xargs -r rm -f
    echo "$(date '+%F %T') бэкап готов: $f ($(du -h "$f" | cut -f1))"
  else
    rm -f "$f.part"
    echo "$(date '+%F %T') бэкап не получился"
    return 1
  fi
}

if [ "${1:-}" = "now" ]; then
  dump
  exit $?
fi

echo "$(date '+%F %T') бэкапы каждый день в 03:30, храню последние $KEEP"
while true; do
  s=$(date +%H:%M:%S | awk -F: '{print $1 * 3600 + $2 * 60 + $3}')
  wait=$(( (AT - s + 86400) % 86400 ))
  [ "$wait" -eq 0 ] && wait=86400
  sleep "$wait"
  dump || true
  sleep 60
done
