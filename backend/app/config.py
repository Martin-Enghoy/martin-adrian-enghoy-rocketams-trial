from pydantic_settings import BaseSettings

class Settings(BaseSettings):
  mock_api_url: str = "http://localhost:9000"
  database_url: str = "sqlite+aiosqlite:///.jobs.db"
  poll_base_interval: float = 2.5 # seconds - above mock API's rate limit
  poll_max_interval: float = 10.0 # backoff cap
  max_retries: int = 1 # auto-retry FATAL reports once

settings = Settings()