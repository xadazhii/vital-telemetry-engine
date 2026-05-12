from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cardio Monitoring Backend"
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/cardio_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    model_config = ConfigDict(env_file=".env")

settings = Settings()
