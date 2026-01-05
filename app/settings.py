from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QG_", env_file=".env", extra="ignore")

    secret_key: str
    db_path: str = "./data/qg.sqlite"

    # Policy
    min_res_p: int = 760
    enable_porn_block: bool = True
    reason_naming: str = "Naming wrong - check you naming"
    reason_porn: str = "No Porn here"

    # Optional external GuessIt REST endpoint (e.g. https://github.com/guessit-io/guessit-rest)
    guessit_rest_url: str | None = None

settings = Settings()
