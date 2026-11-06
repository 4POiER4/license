#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
umask 077
mkdir -p backups
file="backups/licenses-$(date +%Y%m%d-%H%M%S).dump"
temporary="$(mktemp backups/.licenses-backup.XXXXXX)"
trap 'rm -f -- "$temporary"' EXIT
docker compose exec -T db pg_dump -U licenses -d licenses -Fc > "$temporary"
mv -- "$temporary" "$file"
echo "Резервная копия: $file"
