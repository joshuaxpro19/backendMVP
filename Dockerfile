FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Los navegadores de Playwright pesan ~1 GB. Para la demo (sin scraping) se
# puede compilar con --build-arg INSTALAR_PLAYWRIGHT=0.
ARG INSTALAR_PLAYWRIGHT=1
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALAR_PLAYWRIGHT" = "1" ]; then playwright install --with-deps chromium; fi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
