from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "liquid/lfm-2.5-1.2b-thinking:free"
    llm_max_retries: int = 5
    llm_retry_base_delay: float = 3.0
    llm_request_delay: float = 4.0
    llm_max_scenario_explanations: int = 0
    llm_max_tokens: int = 400
    max_technologies: int = 10
    max_industries: int = 12
    max_technology_categories: int = 5
    max_subcategories_per_category: int = 4
    max_technologies_per_industry: int = 4
    arxiv_max_results_per_tech: int = 1
    embedding_model: str = "all-MiniLM-L6-v2"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    app_name: str = "Technology Drivers Identification"

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
