#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ ! -f .env ]; then
  python3 scripts/init_env.py
fi
docker compose up -d --build --wait --wait-timeout 180
python3 - <<'PY'
from pathlib import Path
env = dict(line.split('=', 1) for line in Path('.env').read_text().splitlines() if line and not line.startswith('#'))
print('Приложение запущено: http://localhost:' + env.get('APP_PORT', '8096'))
print('Данные первого входа: .local-access.txt (если пароль уже меняли, используйте новый).')
PY
