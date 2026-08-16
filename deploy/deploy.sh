#!/usr/bin/env bash
# Auto-deploy: pull latest main and rebuild the containers.
# Triggered by the webhook service (see deploy/hooks.json). Safe to run by hand too.
set -euo pipefail

REPO_DIR="${AURUM_REPO_DIR:-/opt/aurum}"
LOG="${AURUM_DEPLOY_LOG:-/var/log/aurum-deploy.log}"
LOCK="/tmp/aurum-deploy.lock"

# flock: if a deploy is already running, skip this one instead of stacking builds.
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "$(date -Is) deploy already running, skipping" >>"$LOG"
  exit 0
fi

{
  echo "===== $(date -Is) deploy start ====="
  cd "$REPO_DIR"
  git fetch --all --prune
  git reset --hard origin/main
  docker compose up -d --build
  docker image prune -f
  echo "===== $(date -Is) deploy done ====="
} >>"$LOG" 2>&1
