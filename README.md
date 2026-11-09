# MVP Backend (FastAPI + PostgreSQL)

API REST para una comunidad vecinal: usuarios con roles, servicios, productos,
pedidos, alertas, noticias externas y un catálogo inicial importado de datos
abiertos.

## Stack

- Python 3.12 + FastAPI + Uvicorn
- SQLAlchemy 2.x + psycopg2-binary
- PostgreSQL 16
- pydantic v2 + pydantic-settings
- httpx + BeautifulSoup + lxml (extracción de fuentes públicas)
- Docker + docker-compose

## Estructura

```
.
├── app/
│   ├── main.py              # Punto de entrada FastAPI y migraciones de arranque
│   ├── config/              # Settings (pydantic-settings)
│   ├── api/routes/          # Endpoints (auth, users, services, products, orders, alerts, news, admin)
│   ├── api/schemas/         # Esquemas de entrada/salida
│   ├── domain/models/       # Entidades SQLAlchemy
│   ├── infrastructure/      # Conexión a la base y migraciones ligeras
│   ├── usecases/            # Autenticación y reglas de acceso
│   ├── services/            # Lógica de negocio por entidad
│   └── scraping/            # INDECI (noticias) y OpenStreetMap (catálogo)
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── .dockerignore
```

## Requisitos (WSL)

- WSL2 con Docker Engine instalado y corriendo
- El proyecto debe estar en el filesystem Linux de WSL (no bajo `/mnt/c/...`)

```bash
# Verificar
docker --version
docker compose version
pwd   # debe ser un path tipo /home/... o /home/user/proyectos/...
```

## Levantar

```bash
# 1. Copiar variables
cp .env.example .env

# 2. Levantar (api + db)
docker compose up --build

# 3. Verificar
curl http://localhost:8000/docs
```

## Detener

```bash
docker compose down        # detener
docker compose down -v     # detener y borrar volumen de Postgres
```

## Catálogo inicial y alertas externas

Dos procesos del backend alimentan la app con datos reales, sin depender de que
los vecinos publiquen primero:

| Fuente | Módulo | Qué aporta | Licencia / condición |
| --- | --- | --- | --- |
| INDECI | `app/scraping/indeci.py` | Reportes, boletines y avisos del portal público de peligros | Portal público del Estado peruano |
| OpenStreetMap (Overpass) | `app/scraping/osm.py` | Negocios y servicios de un radio alrededor de un punto | Datos abiertos, ODbL (requiere atribución) |

No se scrapean redes sociales ni se saltan protecciones: solo se leen páginas
públicas y una API abierta.

### Endpoints

- `GET /api/news` — noticias y alertas importadas. Público, paginado y
  filtrable por `source` y `category` (`reporte`, `boletin`, `aviso`, `otro`).
- `POST /api/admin/news/refresh` — descarga y guarda los reportes vigentes de
  INDECI. Requiere rol **moderador** o **administrador**. Es idempotente:
  actualiza por `source + external_id`, no duplica.
- `POST /api/admin/catalog/seed/osm` — importa lugares de OpenStreetMap.
  Requiere rol **administrador**. Cuerpo opcional:

```json
{ "lat": -5.1945, "lng": -80.6328, "radius_m": 4000, "max_items": 300 }
```

Los lugares importados quedan a nombre de un usuario técnico
(`directorio_vecinal`) y conservan `source`, `source_url`, `external_id`,
dirección, teléfono, web y coordenadas. Un segundo `seed` con el mismo radio
actualiza los existentes en vez de duplicarlos.

Variables opcionales en `.env`:

```
INDECI_URL=https://portal.indeci.gob.pe/informe/informe-de-peligros/
OVERPASS_URL=https://overpass-api.de/api/interpreter
HTTP_TIMEOUT_SECONDS=45
OSM_TIMEOUT_SECONDS=90
```

## Pruebas

```bash
pip install -r requirements.txt pytest
export DATABASE_URL="postgresql+psycopg2://usuario:clave@localhost:5432/mvp_db"
pytest -q
```

Las pruebas usan la base de `DATABASE_URL`. `tests/conftest.py` crea las tablas
que falten y aplica las migraciones idempotentes antes de correrlas, así que
también funcionan sobre una instalación anterior. Las de scraping no tocan la
red: el HTML de INDECI y el JSON de Overpass se simulan.

## Notas

- Servicios en red bridge; `api` se conecta a `db` por nombre de servicio (`POSTGRES_HOST=db`), sin `network_mode: host`.
- Volumen persistente `pgdata` para los datos de PostgreSQL.
- Las migraciones de arranque viven en `app/infrastructure/database/migrations.py`
  y son idempotentes (`ADD COLUMN IF NOT EXISTS`). Alembic queda para cuando el
  esquema se estabilice.
