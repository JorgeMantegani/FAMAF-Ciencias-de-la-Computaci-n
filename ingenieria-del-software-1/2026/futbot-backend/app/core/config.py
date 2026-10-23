from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

"""Configuracion de la aplicacion, leida desde el archivo .env."""
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # base de datos
    database_url: str = "sqlite:///./futbot.db"
    
    #auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=1440, gt=0)
    refresh_enabled: bool = False
    refresh_expire_days: int = Field(default=7, gt=0)
    
    #CORS
    cors_origins_list: list[str] = Field(
        default=["http://localhost:5173"],
        validation_alias=AliasChoices("CORS_ORIGINS", "CORS_ORIGINS_LIST"),
    )
    
     # --- Simulacion de partidos ---
    match_tick_rate: int = 15
    friendly_match_duration_seconds: int = 300
    behavior_timeout_seconds: float = 0.05
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    

settings = Settings()
@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuracion, leyendo el .env una sola vez."""
    return Settings()
