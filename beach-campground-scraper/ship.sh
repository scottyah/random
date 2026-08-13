#!/bin/bash
set -euo pipefail

# Encrypt .env -> .env.encrypted, commit, and push to trigger Gitea Actions deploy.

if [ ! -f .env ]; then
  echo "No .env found. Copy .env.example to .env and fill it in first."
  exit 1
fi

# Encrypt secrets
echo "Encrypting .env -> .env.encrypted..."
sops --encrypt --input-type dotenv --output-type dotenv .env > .env.encrypted
echo "Done."

# Stage, commit, push
git add .env.encrypted
if git diff --cached --quiet .env.encrypted 2>/dev/null; then
  echo "No secret changes to commit."
  echo "Pushing any existing commits..."
else
  git commit -m "update encrypted secrets"
  echo "Committed secret changes."
fi

git push
echo ""
echo "Pushed. Gitea Actions will build and deploy."
