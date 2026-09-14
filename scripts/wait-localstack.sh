#!/usr/bin/env bash
set -euo pipefail
for i in $(seq 1 60); do
  if curl -sf http://localhost:4566/_localstack/health > /dev/null 2>&1; then
    echo "LocalStack saudável"
    exit 0
  fi
  sleep 2
done
echo "LocalStack não respondeu a tempo" >&2
exit 1
