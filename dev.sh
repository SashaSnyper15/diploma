#!/usr/bin/env bash
# Запускает backend (FastAPI, :8000) и админку (Vite, :5173) одной командой.
# Ctrl+C останавливает оба процесса.
#
#   ./dev.sh           — локально и в той же Wi-Fi сети
#   ./dev.sh --public  — плюс публичная ссылка через интернет
#                        (cloudflared, если установлен, иначе localhost.run через ssh)
#   ./dev.sh --public-ssh — публичная ссылка всегда через localhost.run
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

PUBLIC=0
case "${1:-}" in --public|--public-ssh) PUBLIC=1 ;; esac

# --- подготовка окружения (только при первом запуске) ---
if [ ! -x "$BACKEND/.venv/bin/uvicorn" ]; then
  echo "[setup] Создаю venv и ставлю зависимости backend..."
  python3 -m venv "$BACKEND/.venv"
  "$BACKEND/.venv/bin/pip" install -r "$BACKEND/requirements.txt"
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "[setup] Ставлю зависимости frontend..."
  (cd "$FRONTEND" && npm install)
fi

# --- запуск ---
cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Останавливаю сервер и админку..."
  kill 0 2>/dev/null || true
}
# HUP — закрытие окна терминала: без него процессы остаются висеть.
trap cleanup INT TERM HUP EXIT

# Гасим процессы этого проекта, оставшиеся с прошлого запуска (иначе порты заняты).
stale_pids() {
  for pid in $(lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null || true); do
    ps -o command= -p "$pid" | grep -q "$ROOT" && echo "$pid"
  done
  return 0
}
for port in 8000 5173; do
  pids="$(stale_pids "$port")"
  [ -z "$pids" ] && continue
  echo "[setup] Останавливаю старый процесс на порту $port (PID $pids)"
  for pid in $pids; do pkill -TERM -P "$pid" 2>/dev/null || true; kill -TERM "$pid" 2>/dev/null || true; done
  for _ in 1 2 3 4 5; do [ -z "$(stale_pids "$port")" ] && break; sleep 1; done
  for pid in $(stale_pids "$port"); do pkill -KILL -P "$pid" 2>/dev/null || true; kill -KILL "$pid" 2>/dev/null || true; done
done

prefix() { awk -v p="$1" '{ print "[" p "] " $0; fflush() }'; }

(cd "$BACKEND" && exec .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) 2>&1 | prefix api &
(cd "$FRONTEND" && exec npm run dev) 2>&1 | prefix admin &

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"

echo
echo "На этом компьютере:"
echo "  Админка: http://localhost:5173"
echo "  API:     http://localhost:8000"
echo "  Swagger: http://localhost:8000/docs"
if [ -n "$LAN_IP" ]; then
  echo "С других устройств в этой сети:"
  echo "  Админка: http://$LAN_IP:5173"
  echo "  API:     http://$LAN_IP:8000"
  echo "  Swagger: http://$LAN_IP:8000/docs"
fi
echo

# $1 — регулярка публичного адреса, $2 — строка лога, после которой туннель готов
# (cloudflared печатает адрес раньше, чем подключается, и ссылка сначала даёт ошибку 1033).
print_public() {
  awk -v re="$1" -v ready="${2:-}" '{ print "[tunnel] " $0; fflush() }
    url == "" && match($0, re) { url = substr($0, RSTART, RLENGTH) }
    url != "" && !shown && (ready == "" || index($0, ready)) {
      shown = 1
      print ""
      print "Из интернета (с любого устройства):"
      print "  Админка: " url
      print "  API:     " url "/api/v1"
      print "  Swagger: " url "/docs"
      print ""
      fflush()
    }'
}

# --public: cloudflared, если установлен; --public-ssh: всегда localhost.run.
if [ "$PUBLIC" = 1 ] && command -v cloudflared >/dev/null && [ "${1:-}" != "--public-ssh" ]; then
  echo "Поднимаю туннель Cloudflare, ссылка появится после подключения..."
  # Cloudflare Quick Tunnel: без регистрации, адрес меняется при каждом запуске.
  cloudflared tunnel --no-autoupdate --url http://localhost:5173 2>&1 \
    | print_public 'https://[a-z0-9-]+\.trycloudflare\.com' 'Registered tunnel connection' &
elif [ "$PUBLIC" = 1 ]; then
  echo "Поднимаю туннель localhost.run, ссылка появится после подключения..."
  # localhost.run: работает через встроенный ssh, ничего ставить не нужно.
  ssh -T -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 \
    -R 80:localhost:5173 nokey@localhost.run 2>&1 \
    | print_public 'https://[a-z0-9-]+\.lhr\.life' &
fi

wait
