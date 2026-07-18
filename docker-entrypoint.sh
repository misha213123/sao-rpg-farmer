#!/bin/sh
set -eu

python - <<'PY'
from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')
replacements = {
    ':35 — /start': ':45 — /start',
    ':37 — /start': ':49 — /start',
    'Starting guild route at :35 MSK': 'Starting guild route at :45 MSK',
    'Starting arena route at :37 MSK': 'Starting arena route at :49 MSK',
    'Между завершением гильдии и :37 ничего не нажимаем.': 'Между завершением гильдии и :49 ничего не нажимаем.',
    'Guild attacks exhausted; waiting for :37 MSK': 'Guild attacks exhausted; waiting for :49 MSK',
    'now_moscow.minute >= 37': 'now_moscow.minute >= 49',
    'now_moscow.minute == 35': 'now_moscow.minute == 45',
    'Если сервис запустился после :37': 'Если сервис запустился после :49',
}
for old, new in replacements.items():
    text = text.replace(old, new)
path.write_text(text, encoding='utf-8')
PY

exec python -m app.main
