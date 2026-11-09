# DelBarrio

App móvil del barrio: un directorio de **servicios y productos**, un muro de
**favores solidarios** y un **tablero de emergencia**. Además muestra, como
servicios de Economía Local, los **anuncios capturados de Facebook** (scraping),
limpiados y clasificados con **IA**.

- Vecinos publican servicios, productos, favores y emergencias.
- Los anuncios de Facebook se importan con su teléfono y ubicación; un modelo de
  visión (OpenRouter) descarta memes/spam y extrae los datos útiles.
- Sin cuenta se puede mirar; para contactar, publicar o pedir ayuda hay que
  entrar con **celular + contraseña de 6 dígitos**.

---

## Stack

| Capa | Tecnología |
|---|---|
| App móvil | **Expo SDK 58 / React Native 0.88** (Expo Go), React Navigation, TanStack Query |
| Backend | **FastAPI** + SQLAlchemy 2 + Uvicorn |
| Base de datos | **PostgreSQL 16** (Docker) o SQLite en local |
| Scraping | **Playwright** (Chromium) sobre Facebook |
| IA | **OpenRouter** con un modelo de visión (por defecto `google/gemini-2.5-flash`) |
| Túnel | **cloudflared** (expone el backend a internet) + Expo/ngrok (bundle) |
| Contenedores | Docker Compose (api + db) |

```
backendMVP/
├── app/                 # API FastAPI (contrato de la app, scraping, IA)
├── mobile/              # app Expo (React Native)
├── front/               # front web original (solo referencia, no se usa)
├── scripts/             # demo, túnel, importación y datos de ejemplo
├── tests/               # pytest
├── docker-compose.yml   # api + postgres
└── Dockerfile
```

---

## Requisitos

- **Windows + WSL2** con **Docker** (o cualquier Linux/macOS con Docker).
- **Node 22+** y **Python 3.12+**.
- **Expo Go** instalado en el celular (Play Store / App Store).
- Opcional: **API key de OpenRouter** (`sk-or-v1-...`) para la limpieza con IA.

---

## Cómo correr (en orden)

> El backend va **primero**: al arrancar el túnel escribe la URL en
> `mobile/.env`. Expo toma esa URL al empaquetar, así que siempre se inicia
> después del backend.

### 1. Backend + base de datos + túnel

**Windows (PowerShell):**
```powershell
cd C:\Users\Joshua\Proyectos\backendMVP
.\scripts\demo-docker.ps1
```

**WSL / Linux / macOS:**
```bash
cd /mnt/c/Users/Joshua/Proyectos/backendMVP
bash scripts/demo-docker.sh
```

El script:
1. Copia `.env.example` a `.env` si falta.
2. Levanta **api + Postgres** con `docker compose` (compila sin Chromium; para
   scraping usa `-Playwright 1` / `PLAYWRIGHT=1`).
3. Espera a que responda `/api/salud`.
4. Abre un túnel de Cloudflare y espera a que resuelva.
5. Escribe la URL en `mobile/.env` e imprime:

```
==============================================
 API pública: https://algo-random.trycloudflare.com
 Docs:        https://algo-random.trycloudflare.com/docs
==============================================
```

Déjalo abierto. `Ctrl+C` apaga el túnel **y** los contenedores.

### 2. App móvil

En otra terminal:

```powershell
cd C:\Users\Joshua\Proyectos\backendMVP\mobile
npm install
npm run tunnel:clear        # túnel de Expo (ngrok, sin cuenta)
```

Escanea el QR con **Expo Go**.

- Si el celular está en la **misma WiFi**, usa `npm run lan:clear` (más rápido,
  sin ngrok) y escanea el QR `exp://<tu-ip>:8081`.
- **Cada vez que cambie la URL del túnel** hay que reiniciar Expo con `--clear`.

### 3. Dentro de la app

1. **Mi cuenta → Crear cuenta**: nombre, **celular (9 dígitos)**, contraseña
   **de solo números (mínimo 6)**, sector y aceptar privacidad.
2. **Local / Favores / Emergencia**: publicar, buscar y contactar por WhatsApp.
3. **Mi actividad → Editar**: cambiar datos, fotos y WhatsApp de tus publicaciones.
4. **Perfil → Revisión con IA**: pegar la API key de OpenRouter y limpiar los
   anuncios de Facebook.

---

## Revisión con IA (opcional)

`Perfil → Revisión con IA`:

- Pega la **API key de OpenRouter** (se guarda en el servidor, nunca se devuelve).
- Modelo por defecto: `google/gemini-2.5-flash` (se puede cambiar ahí mismo).
- **Revisar todas**: por cada publicación scrapeada, la IA lee el texto **y la
  imagen**, traduce, decide si es una oferta real y extrae **teléfono y
  ubicación** (aunque solo aparezcan en la foto).
- Lo rechazado (memes, "ver más", spam) **desaparece de Economía Local**; lo
  aprobado usa el título, descripción, categoría, teléfono y ubicación de la IA.

También se puede configurar en `.env`:

```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=google/gemini-2.5-flash
```

### Automatización

Un hilo dentro de la API (arranca con el servidor):

| Tarea | Frecuencia | Condición |
|---|---|---|
| Scrapeo de Facebook | `SCRAPE_CADA_HORAS` (6 h) | hay sesión de Facebook (`FB_EMAIL`/`FB_PASSWORD` o `data/fb_state.json`) |
| Limpieza con IA | cada minuto | hay API key y publicaciones pendientes (`IA_LOTE` = 12) |

Si algo falla, espera 30 min antes de reintentar (no satura Facebook ni OpenRouter).
El estado (último/próximo scrapeo, errores) se ve en **Perfil → Revisión con IA**.

---

## Variables de entorno (`.env`)

| Variable | Para qué | Default |
|---|---|---|
| `DATABASE_URL` | conexión SQLAlchemy | Postgres del compose |
| `SECRET_KEY` | firma de los JWT | (cámbiala en producción) |
| `FB_EMAIL` / `FB_PASSWORD` | login del scraper | vacío |
| `FB_STATE_PATH` | sesión guardada de Facebook | `data/fb_state.json` |
| `SCRAPING_CITY` / `SCRAPING_QUERIES` | qué buscar | Piura, 6 consultas |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | revisión con IA | vacío / `google/gemini-2.5-flash` |
| `AUTOMATIZACION` / `SCRAPE_CADA_HORAS` / `IA_AUTO` / `IA_LOTE` | planificador | `true` / `6` / `true` / `12` |

La app móvil usa `EXPO_PUBLIC_API_URL` en `mobile/.env` (lo reescribe el script).

---

## Comandos útiles

```bash
# Tests del backend (SQLite)
DATABASE_URL=sqlite:///./test.db python -m pytest -q

# Importar un JSON del scraper con sus imágenes
python scripts/import_scraping_json.py ruta/resultados.json

# Cargar 6 leads de ejemplo (sin sesión de Facebook)
python scripts/seed_demo_scraping.py

# Apagar el stack
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/Joshua/Proyectos/backendMVP && docker compose down"
```

## API

Documentación interactiva en `https://<tu-tunel>/docs`. Las rutas que usa la
app son `/api/registro`, `/api/login`, `/api/perfil`, `/api/zonas`,
`/api/publicaciones`, `/api/fotos`, `/api/mis-publicaciones`, `/api/vistos`,
`/api/reportes`, `/api/emergencia/*`, `/api/notificaciones` y `/api/ia/*`.

## Notas

- La app no pide correo: la cuenta se identifica por el celular.
- Sin sesión, la API **no** devuelve teléfono, Yape ni la ubicación exacta.
- La ubicación publicada se muestra aproximada (jitter de 300-500 m).
- `front/` es el front web original de un compañero; se conserva solo como
  referencia. La app que se usa es `mobile/`.
