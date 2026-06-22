#!/bin/bash
: "${PROJECT_NAME:=priceless}"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE="${HOME}/.proton-chrome-seed"
CDP_PORT=9222

echo "============================================================"
echo "Proton session seed (for Human Verification / CAPTCHA)"
echo "============================================================"
echo

if ! docker ps --format '{{.Names}}' | grep -qx "$PROJECT_NAME"; then
    echo "ERROR: Docker container '$PROJECT_NAME' is not running."
    echo "Start it first: make start"
    exit 1
fi

if curl -sf "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
    echo "OK: Chrome remote debugging is active on port ${CDP_PORT}."
else
    echo "Chrome is NOT listening on port ${CDP_PORT} yet."
    echo
    echo "IMPORTANT: Quit Chrome completely first (Cmd+Q), then run Step 1"
    echo "in a separate terminal — do NOT use your normal Chrome window."
    echo
    echo "Step 1 — start Chrome with remote debugging:"
    echo
    echo "  \"$CHROME\" \\"
    echo "    --remote-debugging-port=${CDP_PORT} \\"
    echo "    --user-data-dir=\"$PROFILE\" \\"
    echo "    https://account.proton.me/login"
    echo
    echo "Step 2 — in that Chrome window:"
    echo "  - Sign in with the email/password from your .env"
    echo "  - Complete Human Verification if shown"
    echo "  - Wait until you see Proton Mail inbox or the apps page"
    echo
    echo "When Chrome is running on port ${CDP_PORT}, re-run: make proton-seed-session"
    exit 1
fi

echo
echo "Step 3 — Press Enter to save the session for Docker..."
read -r _

docker exec -i -t "$PROJECT_NAME" \
  poetry run python -m proton_email.seed_session "$@"
