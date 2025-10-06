from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application configuration model using Pydantic.
    """
    # --- LLM Configuration ---
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"

    # --- Execution Configuration ---
    USE_DOCKER_EXECUTION: bool = False
    DOCKER_IMAGE: str = "python:3.11-slim"
    CODE_EXECUTION_TIMEOUT: int = 60

    # --- Application Settings ---
    HISTORY_LIMIT: int = 5

    # --- Data Manager Configuration ---
    MAX_CSV_SIZE_MB: int = 100
    MAX_ROWS_PREVIEW: int = 10

    # --- Path Configuration ---
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "sample_data"
    OUTPUT_DIR: Path = PROJECT_ROOT / "outputs"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    def __init__(self, **values):
        super().__init__(**values)
        self.OUTPUT_DIR.mkdir(exist_ok=True)

settings = Settings()