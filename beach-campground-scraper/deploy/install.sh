#!/usr/bin/env bash
#
# One-command setup on your server. Idempotent -- safe to re-run.
#
#   ./deploy/install.sh
#
# Does: venv + deps -> resolve facility IDs -> verify -> install systemd timer.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

PY="${PYTHON:-python3}"
VENV="$HERE/.venv"

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33m    %s\033[0m\n' "$*"; }
die() { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

say "Creating virtualenv"
[ -d "$VENV" ] || "$PY" -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt
echo "    $($VENV/bin/python --version)"

say "Config"
if [ ! -f config.yaml ]; then
    cp config.example.yaml config.yaml
    echo "    created config.yaml from the example"
    warn "Edit config.yaml to add a notifier -- console-only means you"
    warn "will never actually hear about an opening."
else
    echo "    config.yaml already exists, leaving it alone"
fi

say "Running tests"
"$VENV/bin/python" -m unittest discover -s tests -q 2>&1 | tail -3

say "Resolving ReserveCalifornia facility IDs"
if "$VENV/bin/python" -m campscout discover --write; then
    echo "    IDs written to data/campgrounds.yaml"
else
    die "discovery failed -- check outbound HTTPS to the ReserveCalifornia API host (see BASE in campscout/providers/reserve_california.py), then re-run"
fi

say "Verifying we can actually read a campground"
"$VENV/bin/python" -m campscout sites san_elijo | head -15 || \
    warn "site listing failed; check the IDs in data/campgrounds.yaml"

say "First scan"
"$VENV/bin/python" -m campscout scan

say "Installing systemd timer"
if command -v systemctl >/dev/null 2>&1 && [ -d /etc/systemd/system ]; then
    if [ "$(id -u)" -ne 0 ]; then
        warn "not root; skipping. To install:"
        warn "  sudo env INSTALL_DIR=$HERE $HERE/deploy/install.sh --timer-only"
    else
        sed "s|/srv/campscout|$HERE|g" deploy/campscout.service > /etc/systemd/system/campscout.service
        cp deploy/campscout.timer /etc/systemd/system/campscout.timer
        systemctl daemon-reload
        systemctl enable --now campscout.timer
        echo "    enabled; next run:"
        systemctl list-timers campscout.timer --no-pager | head -3
    fi
else
    warn "no systemd here. Add this to your crontab instead:"
    warn "  */10 * * * * cd $HERE && $VENV/bin/python -m campscout scan >> /var/log/campscout.log 2>&1"
fi

say "Status"
"$VENV/bin/python" -m campscout status || true

cat <<EOF

Next:
  1. Add a notifier (ntfy is easiest) in config.yaml, then:
       $VENV/bin/python -m campscout test-notify
  2. Set heartbeat.url to a healthchecks.io ping URL so you are told if
     this host ever stops checking. Without it, a dead scraper is
     indistinguishable from a quiet campground.
  3. Check on it any time with:
       $VENV/bin/python -m campscout status
EOF
