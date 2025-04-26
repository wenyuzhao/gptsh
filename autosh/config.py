import sys
from pydantic import BaseModel, Field
from pathlib import Path
import tomllib

import rich

USER_CONFIG_PATH = Path.home() / ".config" / "autosh" / "config.toml"


class EmptyConfig(BaseModel): ...


class SearchConfig(BaseModel):
    tavily_api_key: str = Field(..., description="Tavily API key.")


class WebConfig(BaseModel):
    tavily_api_key: str = Field(..., description="Tavily API key.")


class Plugins(BaseModel):
    calc: EmptyConfig | None = None
    cli: EmptyConfig | None = None
    clock: EmptyConfig | None = None
    code: EmptyConfig | None = None
    search: SearchConfig | None = None
    web: WebConfig | None = None


class Config(BaseModel):
    model: str = Field(default="openai/gpt-4.1", description="The LLM model to use")
    think_model: str = Field(
        default="openai/o4-mini-high",
        description="The LLM model to use for reasoning before executing commands",
    )
    api_key: str | None = Field(default=None, description="OpenRouter API key.")
    repl_banner: str = Field(
        default="🦄 Welcome to [cyan]autosh[/cyan]. The AI-powered, noob-friendly interactive shell.",
        description="The banner for the REPL.",
    )
    repl_prompt: str = Field(
        default="{short_cwd}> ",
        description="The prompt for the REPL user input.",
    )

    plugins: Plugins = Field(
        default_factory=Plugins,
        description="Plugin configuration. Set to null to disable the plugin.",
    )

    @staticmethod
    def load() -> "Config":
        if not USER_CONFIG_PATH.is_file():
            # Copy config.template.toml to USER_CONFIG_PATH
            USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            template = Path(__file__).parent / "config.template.toml"
            USER_CONFIG_PATH.write_text(template.read_text())
        if USER_CONFIG_PATH.is_file():
            try:
                doc = tomllib.loads(USER_CONFIG_PATH.read_text())
                main = doc.get("autosh", {})
                plugins = Plugins(**doc.get("plugins", {}))
                config = Config.model_validate({**main, "plugins": plugins})
            except tomllib.TOMLDecodeError as e:
                rich.print(f"[bold red]Error:[/bold red] invalid config file: {e}")
                sys.exit(1)
        else:
            config = Config()
        return config


CONFIG = Config.load()


class CLIOptions(BaseModel):
    yes: bool = False
    quiet: bool = False
    think: bool = False
    start_repl_after_prompt: bool = False

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
