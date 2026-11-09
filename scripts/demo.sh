#!/usr/bin/env bash
# Demo: backend en :8000 + tÃºnel pÃºblico de Cloudflare
#
#   ./scripts/demo.sh
#
# Levanta uvicorn con SQLite (data/demo.db), abre un tÃºnel rÃ¡pido de Cloudflare,
# imprime la URL pÃºblica y la escribe en mobile/.env para que Expo la use.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

HOST_API="${HOST_API:-127.0.0.1}"
PUERTO="${PUERTO:-8000}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/demo.db}"

mkdir -p data

limpiar() {
  [[ -n "${PID_UVICORN:-}" ]] && kill "$PID_UVICORN" 2>/dev/null || true
  [[ -n "${PID_TUNEL:-}" ]] && kill "$PID_TUNEL" 2>/dev/null || true
}
trap limpiar EXIT INT TERM

# --- 1. backend -------------------------------------------------------------
python3 -m uvicorn app.main:app --host "$HOST_API" --port "$PUERTO" &
PID_UVICORN=$!
echo "Backend iniciado (pid $PID_UVICORN) en http://${HOST_API}:${PUERTO}"

for _ in $(seq 1 40); do
  if curl -fsS "http://${HOST_API}:${PUERTO}/api/salud" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS "http://${HOST_API}:${PUERTO}/api/salud" >/dev/null 2>&1; then
  echo "El backend no respondiÃ³ en ${HOST_API}:${PUERTO}." >&2
  exit 1
fi

# --- 2. cloudflared ---------------------------------------------------------
mkdir -p tools
EXE="tools/cloudflared"
if ! command -v cloudflared >/dev/null 2>&1; then
  if [[ ! -x "$EXE" ]]; then
    echo "Descargando cloudflaredâ€¦"
    case "$(uname -s)" in
      Linux)  SUF="linux-amd64" ;;
      Darwin) SUF="darwin-amd64" ;;
      *) echo "Sistema no soportado: usa cloudflared del sistema." >&2; exit 1 ;;
    esac
    curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-${SUF}" -o "$EXE"
    chmod +x "$EXE"
  fi
  CLOUDFLARED="$EXE"
else
  CLOUDFLARED="cloudflared"
fi

LOG="$(mktemp)"
"$CLOUDFLARED" tunnel --url "http://${HOST_API}:${PUERTO}" --no-autoupdate >"$LOG" 2>&1 &
PID_TUNEL=$!

URL=""
for _ in $(seq 1 80); do
  sleep 0.5
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -n1 || true)"
  [[ -n "$URL" ]] && break
done

if [[ -z "$URL" ]]; then
  echo "No se pudo obtener la URL del tÃºnel. Log: $LOG" >&2
  tail -n 30 "$LOG" >&2 || true
  exit 1
fi

# El DNS del tÃºnel reciÃ©n creado tarda unos segundos: esperamos a que responda.
echo "Esperando a que el tÃºnel respondaâ€¦"
for _ in $(seq 1 60); do
  if curl -fsS "$URL/api/salud" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if [[ -d mobile ]]; then
  echo "EXPO_PUBLIC_API_URL=$URL" > mobile/.env
fi

echo ""
echo "=============================================="
echo " API pÃºblica: $URL"
echo " Docs:        $URL/docs"
echo "=============================================="
echo ""
echo "mobile/.env actualizado con esa URL."
echo "Ahora, en otra terminal:"
echo "    cd mobile"
echo "    npx expo start --tunnel ngrok --clear"
echo ""
echo "Ctrl+C para detener el backend y el tÃºnel."

wait "$PID_TUNEL"
