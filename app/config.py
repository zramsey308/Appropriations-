from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/appropriations.db"
    attachments_dir: str = "./data/attachments"

    class Config:
        env_file = ".env"


settings = Settings()
