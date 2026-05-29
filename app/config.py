from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    devin_api_key: str = ""
    github_token: str = ""
    github_repo: str = ""  # e.g. "your-username/superset"
    webhook_secret: str = ""
    devin_trigger_label: str = "devin-fix"
    database_path: str = "data/sessions.db"
    poll_interval_seconds: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
