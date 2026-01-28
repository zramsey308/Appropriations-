from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://appropriations:appropriations_secret@localhost:5432/appropriations_db"
    attachments_dir: str = "./data/attachments"

    class Config:
        env_file = ".env"


settings = Settings()
