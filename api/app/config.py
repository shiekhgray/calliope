from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    music_root: str = "/music"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    lastfm_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
