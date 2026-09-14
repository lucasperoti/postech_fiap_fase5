#!/usr/bin/env bash
set -euo pipefail
docker compose up -d
./scripts/wait-localstack.sh
echo "LocalStack pronto em http://localhost:4566"
