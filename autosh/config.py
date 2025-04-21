from pydantic import BaseModel, Field
from pathlib import Path
import tomllib

USER_CONFIG_PATH = Path.home() / ".config" / "autosh" / "config.toml"


class Config(BaseModel):
    yes: bool = Field(
        default=False,
        description="Automatically answer yes to all prompts.",
    )
    quiet: bool = Field(
        default=False,
        description="Suppress all output.",
    )

    @staticmethod
    def load() -> "Config":
        if USER_CONFIG_PATH.is_file():
            config = Config(**tomllib.loads(USER_CONFIG_PATH.read_text()))
        else:
            config = Config()
        return config


CONFIG = Config.load()
