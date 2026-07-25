#!/bin/sh
set -eu

# Start both Telegram accounts through the stable launcher.
exec python -m app.multi_account_launcher
