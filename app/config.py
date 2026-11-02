"""Application settings, loaded from environment variables.

Values are read from real environment variables first, then from a local
.env file if one exists. This is what lets the same code run on a laptop
(SQLite) and in production (Postgres): only the environment changes.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Each field below maps to an environment variable of the same name,
    # ignoring case: secret_key <- SECRET_KEY, and so on.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Used to sign JWT tokens. It has no default on purpose: the app refuses to
    # start without a real secret, rather than quietly using a guessable one.
    secret_key: str = Field(min_length=32)

    # Where the database lives. Defaults to a local SQLite file.
    database_url: str = "sqlite:///./task_manager.db"

    # How long a login token stays valid.
    access_token_expire_minutes: int = Field(default=30, gt=0)


# A single shared instance that the rest of the app imports.
settings = Settings()
