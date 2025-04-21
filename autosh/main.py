import os
from pathlib import Path
from typing import Annotated
import typer
import asyncio
import dotenv

from autosh.config import CLI_OPTIONS, CONFIG
from .session import Session
import sys


app = typer.Typer(
    no_args_is_help=False,
    add_completion=False,
    context_settings=dict(help_option_names=["-h", "--help"]),
    pretty_exceptions_short=True,
    pretty_exceptions_show_locals=False,
    help="Autosh is a command line tool that helps you automate your tasks using LLMs.",
)


async def async_run(prompt: str | None):
    session = Session()
    if prompt and sys.stdin.isatty():
        # No piped stdin, just run the prompt
        if Path(prompt).is_file():
            # If the prompt is a file, read it and execute it
            with open(prompt, "r") as f:
                prompt = f.read()
        await session.exec_one(prompt)
    elif prompt and not sys.stdin.isatty():
        # Piped stdin with a prompt. Execute the prompt with the piped stdin as input data.
        raise NotImplementedError("Not implemented")
    elif not prompt and not sys.stdin.isatty():
        # Piped stdin without prompt, treat piped stdin as a prompt.
        raise NotImplementedError("Not implemented")
    else:
        await session.run_repl()


@app.command()
def run(
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Automatically answer yes to all prompts.",
            is_eager=True,
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress all output except for errors.",
            is_eager=True,
        ),
    ] = False,
    prompt_or_file: Annotated[str | None, typer.Argument()] = None,
    args: Annotated[list[str] | None, typer.Argument()] = None,
):
    dotenv.load_dotenv()
    if CONFIG.api_key is None:
        if "OPENROUTER_API_KEY" in os.environ:
            CONFIG.api_key = os.environ["OPENROUTER_API_KEY"]
        else:
            raise ValueError(
                "No OpenRouter API key found. Please set the OPENROUTER_API_KEY environment variable."
            )
    CLI_OPTIONS.yes = yes
    CLI_OPTIONS.quiet = quiet
    asyncio.run(async_run(prompt_or_file))


def main():
    app()
