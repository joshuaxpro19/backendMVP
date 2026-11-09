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

    # Fuentes externas (scraping e importación de catálogo)
    indeci_url: str = "https://portal.indeci.gob.pe/informe/informe-de-peligros/"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    http_timeout_seconds: int = 45
    osm_timeout_seconds: int = 90

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

