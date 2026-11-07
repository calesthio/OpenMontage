#!/usr/bin/env bash
# .kilo/hooks/pre-push.sh — блокирует файлы > 90 МБ и секреты в коммите
set -euo pipefail

MAX_WARN_MB=50
MAX_BLOCK_MB=90
GITHUB_LIMIT_MB=100

SECRET_PATTERNS=(
  '\.env'
  'kaggle\.json'
  'API_KEY'
  'SECRET_KEY'
  'PRIVATE_KEY'
  'ACCESS_TOKEN'
  'sk-'
  'ghp_'
)

echo "=== Pre-push hygiene check ==="

# Проверка размеров файлов в staged коммите
for file in $(git diff --cached --name-only); do
  if [ -f "$file" ]; then
    size_bytes=$(stat -c%s "$file" 2>/dev/null || echo 0)
    size_mb=$(( size_bytes / 1024 / 1024 ))
    if [ "$size_mb" -gt "$MAX_BLOCK_MB" ]; then
      echo "BLOCKED: $file is ${size_mb} MB (> ${MAX_BLOCK_MB} MB limit)"
      exit 1
    elif [ "$size_mb" -gt "$MAX_WARN_MB" ]; then
      echo "WARNING: $file is ${size_mb} MB (> ${MAX_WARN_MB} MB warning threshold)"
    fi
  fi
done

# Проверка секретов
for pattern in "${SECRET_PATTERNS[@]}"; do
  if git diff --cached | grep -qiE "$pattern"; then
    echo "BLOCKED: potential secret matching '$pattern' found in staged diff"
    exit 1
  fi
done

echo "=== Pre-push hygiene check PASSED ==="
exit 0