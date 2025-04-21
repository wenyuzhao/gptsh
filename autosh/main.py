import os
from pathlib import Path
import rich
import typer
import asyncio
import dotenv
from rich.columns import Columns
from rich.panel import Panel
import argparse

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


async def start_session(prompt: str | None, args: list[str]):
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


def print_help():
    cmd = Path(sys.argv[0]).name
    rich.print(
        f"\n [bold yellow]Usage:[/bold yellow] [bold]{cmd} [OPTIONS] [--] [PROMPT_OR_FILE] [ARGS]...[/bold]\n"
    )

    args = [
        ["prompt_or_file", "[PROMPT_OR_FILE]", "The prompt or file to execute."],
        ["args", "[ARGS]...", "The arguments to pass to the script."],
    ]
    options = [
        ["--yes", "-y", "Auto confirm all prompts."],
        ["--quiet", "-q", "Suppress all output."],
        ["--help", "-h", "Show this message and exit."],
    ]

    rich.print(
        Panel.fit(
            Columns(
                [
                    "\n".join([a[0] for a in args]),
                    "\n".join([f"[bold yellow]\\{a[1]}[/bold yellow]" for a in args]),
                    "\n".join(["   " + a[2] for a in args]),
                ],
                padding=(0, 3),
            ),
            title="[dim]Arguments[/dim]",
            title_align="left",
            padding=(0, 3),
        )
    )

    rich.print(
        Panel.fit(
            Columns(
                [
                    "\n".join([f"[bold blue]{o[0]}[/bold blue]" for o in options]),
                    "\n".join([f"[bold green]{o[1]}[/bold green]" for o in options]),
                    "\n".join(["    " + o[2] for o in options]),
                ],
                padding=(0, 2),
            ),
            title="[dim]Options[/dim]",
            title_align="left",
            padding=(0, 3),
        )
    )


def parse_args() -> tuple[str | None, list[str]]:
    p = argparse.ArgumentParser(add_help=False, exit_on_error=False)

    p.add_argument("--help", "-h", action="store_true")
    p.add_argument("--yes", "-y", action="store_true")
    p.add_argument("--quiet", "-q", action="store_true")
    p.add_argument("PROMPT_OR_FILE", nargs="?", default=None)
    p.add_argument("ARGS", nargs=argparse.REMAINDER)

    try:
        args = p.parse_args()
    except argparse.ArgumentError as e:
        rich.print(f"[bold red]Error:[/bold red] {str(e)}")
        print_help()
        sys.exit(1)

    if args.help:
        print_help()
        sys.exit(0)

    CLI_OPTIONS.yes = args.yes
    CLI_OPTIONS.quiet = args.quiet

    prompt = args.PROMPT_OR_FILE.strip() if args.PROMPT_OR_FILE else None

    if prompt == "":
        prompt = None

    return prompt, (args.ARGS or [])


def main():
    dotenv.load_dotenv()
    prompt, args = parse_args()

    if CONFIG.api_key is None:
        if key := os.getenv("OPENROUTER_API_KEY"):
            CONFIG.api_key = key
        else:
            rich.print(
                "[bold red]Error:[/bold red] No API key found. Please set the OPENROUTER_API_KEY environment variable or add it to your config file."
            )
            sys.exit(1)
    try:
        asyncio.run(start_session(prompt, args))
    except (KeyboardInterrupt, EOFError):
        rich.print("\n[bold red]Aborted.[/bold red]")
        sys.exit(1)
