#!/usr/bin/env bash
# Возвращает проект к первоначальному виду:
#   - БД: удаляются все проекты, проверки и аудит, создаётся заново demo-проект;
#   - кэши: __pycache__, кэш Vite, сборка frontend/dist.
# venv и node_modules не трогаются.
#
#   ./reset.sh      — с подтверждением
#   ./reset.sh -y   — без подтверждения
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

if [ "${1:-}" != "-y" ]; then
  read -r -p "Все данные в БД будут удалены. Продолжить? [y/N] " answer
  case "$answer" in
    [yYдД]*) ;;
    *) echo "Отменено."; exit 0 ;;
  esac
fi

if [ ! -x "$BACKEND/.venv/bin/python" ]; then
  echo "Нет backend/.venv — сначала запустите ./dev.sh"
  exit 1
fi

echo "Сбрасываю БД..."
(cd "$BACKEND" && .venv/bin/python -m app.reset_db)

echo "Чищу кэши..."
find "$BACKEND" -path "$BACKEND/.venv" -prune -o -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -rf "$FRONTEND/node_modules/.vite" "$FRONTEND/dist"

echo "Готово."
