from typing import Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MVP API"
    debug: bool = False

    # Security
    secret_key: str = "change-this-secret-key-in-production"
    security: Optional[str] = None  # fallback if SECURITY is defined in .env
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # PostgreSQL
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgers_password: Optional[str] = None  # fallback for typo in .env
    postgres_db: str = "mvp_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    database_url: Optional[str] = None

    # Revisión de publicaciones de Facebook con IA (OpenRouter)
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_base: str = "https://openrouter.ai/api/v1"
    ia_max_imagen_kb: int = 1200

    # Automatización: scrapear cada N horas y limpiar con IA
    automatizacion: bool = True
    scrape_cada_horas: int = 6
    ia_auto: bool = True
    ia_lote: int = 12

    # Fotos subidas por el front (data URL -> archivo, servido en /fotos/*)
    fotos_dir: str = "data/fotos"

    # Facebook scraping
    fb_email: Optional[str] = None
    fb_password: Optional[str] = None
    fb_state_path: str = "data/fb_state.json"
    scraping_headless: bool = True
    scraping_images_dir: str = "data/scraping_images"
    scraping_max_images: int = 60
    scraping_city: str = "Piura"
    scraping_localities: str = (
        "piura,castilla,catacaos,sullana,paita,talara,los organos,"
        "veintiseis de octubre,26 de octubre,querecotillo,la arena,la huaca,"
        "bellavista,morropon,huancabamba,manuel montero"
    )
    scraping_queries: str = (
        "carpintero Piura,ofrezco mis servicios Piura,enfermera Piura ofrece servicio,"
        "albañil Piura,electricista Piura,plomero Piura"
    )

    @property
    def locality_list(self) -> list[str]:
        return [item.strip() for item in self.scraping_localities.split(",") if item.strip()]

    @property
    def default_queries(self) -> list[str]:
        return [item.strip() for item in self.scraping_queries.split(",") if item.strip()]

    def model_post_init(self, __context):
        if self.security and self.secret_key == "change-this-secret-key-in-production":
            self.secret_key = self.security
        if self.postgers_password and self.postgres_password == "postgres":
            self.postgres_password = self.postgers_password
        if not self.database_url:
            self.database_url = (
                f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )


settings = Settings()

