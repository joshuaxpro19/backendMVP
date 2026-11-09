#!/usr/bin/env bash
# Demo con Docker: api + Postgres + túnel público de Cloudflare.
#
#   ./scripts/demo-docker.sh            # build normal
#   PLAYWRIGHT=1 ./scripts/demo-docker.sh   # incluye Chromium (scraping)
#
# Requiere Docker Compose. Escribe la URL pública en mobile/.env y deja el
# stack apagado al salir (Ctrl+C).

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

HOST_API="${HOST_API:-127.0.0.1}"
PUERTO="${PUERTO:-8000}"
PLAYWRIGHT="${PLAYWRIGHT:-0}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker no está instalado o no está en el PATH." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Creando .env a partir de .env.example…"
  cp .env.example .env
fi

limpiar() {
  [[ -n "${PID_TUNEL:-}" ]] && kill "$PID_TUNEL" 2>/dev/null || true
  echo "Deteniendo contenedores…"
  docker compose down --remove-orphans >/dev/null 2>&1 || true
}
trap limpiar EXIT INT TERM

# --- 1. stack ---------------------------------------------------------------
echo "Construyendo y levantando api + db (Playwright=${PLAYWRIGHT})…"
INSTALAR_PLAYWRIGHT="$PLAYWRIGHT" docker compose up -d --build

echo "Esperando a que el backend responda en http://${HOST_API}:${PUERTO}…"
LISTO=0
for _ in $(seq 1 120); do
  if curl -fsS "http://${HOST_API}:${PUERTO}/api/salud" >/dev/null 2>&1; then
    LISTO=1
    break
  fi
  sleep 2
done

if [[ "$LISTO" -ne 1 ]]; then
  echo "El backend no respondió. Últimos logs:" >&2
  docker compose logs --tail=60 api >&2 || true
  exit 1
fi
echo "Backend arriba."

curl -fsS "http://${HOST_API}:${PUERTO}/api/zonas" >/dev/null   # smoke rápido
curl -fsS "http://${HOST_API}:${PUERTO}/api/publicaciones?limit=1" >/dev/null

# --- 2. cloudflared ---------------------------------------------------------
mkdir -p tools
EXE="tools/cloudflared"
if ! command -v cloudflared >/dev/null 2>&1; then
  if [[ ! -x "$EXE" ]]; then
    echo "Descargando cloudflared…"
    case "$(uname -s)" in
      Linux)  SUF="linux-amd64" ;;
      Darwin) SUF="darwin-amd64" ;;
      *) echo "Sistema no soportado: instala cloudflared del sistema." >&2; exit 1 ;;
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
  echo "No se pudo obtener la URL del túnel. Log: $LOG" >&2
  tail -n 30 "$LOG" >&2 || true
  exit 1
fi

echo "Esperando a que el túnel responda…"
for _ in $(seq 1 60); do
  curl -fsS "$URL/api/salud" >/dev/null 2>&1 && break
  sleep 0.5
done

# --- 3. todo listo ----------------------------------------------------------
if [[ -d mobile ]]; then
  echo "EXPO_PUBLIC_API_URL=$URL" > mobile/.env
fi

echo ""
echo "=============================================="
echo " API pública: $URL"
echo " Docs:        $URL/docs"
echo "=============================================="
echo ""
echo "mobile/.env actualizado con esa URL."
echo "Ahora, en otra terminal:"
echo "    cd mobile"
echo "    npx expo start --tunnel ngrok --clear"
echo ""
echo "Si cambia la URL del túnel, reinicia Expo con --clear."
echo ""
echo "Ctrl+C para detener el túnel y los contenedores."

wait "$PID_TUNEL"
