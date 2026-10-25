#!/bin/sh
set -e
printenv | grep -E '^(PG_|PYTHONUNBUFFERED)' | sed 's/^/export /; s/=/="/; s/$/"/' > /app/.cron_env
echo '*/2 * * * * . /app/.cron_env; cd /app && flock -n /tmp/tick.lock /app/.venv/bin/python -m etl.tick >> /proc/1/fd/1 2>> /proc/1/fd/2' > /etc/crontabs/root
exec crond -f -l 8 -L /dev/stdout
