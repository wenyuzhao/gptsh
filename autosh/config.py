import sys
from pydantic import BaseModel, Field
from pathlib import Path
import tomllib

USER_CONFIG_PATH = Path.home() / ".config" / "autosh" / "config.toml"


class Config(BaseModel):
    model: str = Field(default="openai/gpt-4.1", description="The LLM model to use")
    api_key: str | None = Field(default=None, description="OpenRouter API key.")

    @staticmethod
    def load() -> "Config":
        if USER_CONFIG_PATH.is_file():
            config = Config(**tomllib.loads(USER_CONFIG_PATH.read_text()))
        else:
            config = Config()
        return config


CONFIG = Config.load()


class CLIOptions(BaseModel):
    yes: bool = False
    quiet: bool = False

    prompt: str | None = None
    """The prompt to execute"""

    script: Path | None = None
    """The scripe providing the prompt"""

    stdin_is_script: bool = False
    """STDIN is a script, not a piped input."""

    args: list[str] = Field(default_factory=list, description="Command line arguments")

    def stdin_has_data(self) -> bool:
        """Check if stdin has data."""
        return not sys.stdin.isatty() and not CLI_OPTIONS.stdin_is_script


CLI_OPTIONS = CLIOptions()
