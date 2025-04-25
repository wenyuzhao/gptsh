import os

os.environ["AGENTIA_DISABLE_PLUGINS"] = "1"

from pathlib import Path
import rich
import typer
import asyncio
from rich.columns import Columns
from rich.panel import Panel
import argparse

from autosh.config import CLI_OPTIONS, CONFIG, USER_CONFIG_PATH
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
    CLI_OPTIONS.args = args
    session = Session()
    os.environ["OPENROUTER_HAS_REASONING"] = "false"
    os.environ["OPENROUTER_INCLUDE_REASONING"] = "false"
    await session.init()
    piped_stdin = not sys.stdin.isatty()
    piped_stdout = not sys.stdout.isatty()
    if (not CLI_OPTIONS.yes) and (piped_stdin or piped_stdout):
        rich.print(
            "[bold red]Error:[/bold red] [red]--yes (-y) is required when using piped stdin or stdout.[/red]",
            file=sys.stderr,
        )
        sys.exit(1)
    if CLI_OPTIONS.start_repl_after_prompt:
        if piped_stdin or piped_stdout:
            rich.print(
                "[bold red]Error:[/bold red] [red]--repl is only available when not using piped stdin or stdout.[/red]",
                file=sys.stderr,
            )
            sys.exit(1)

    if prompt:
        # No piped stdin, just run the prompt
        if Path(prompt).is_file():
            # Prompt is a file, read it and execute it
            await session.exec_script(Path(prompt))
        else:
            # Prompt is a string, execute it directly
            await session.exec_prompt(prompt)
    elif not prompt and not sys.stdin.isatty():
        # Piped stdin without prompt, treat piped stdin as a prompt.
        await session.exec_from_stdin()
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
        [
            "--model",
            "-m",
            f"The LLM model to use. [dim]Default: {CONFIG.model} ({CONFIG.think_model} for reasoning).[/dim]",
        ],
        ["--think", "", "Use the reasoning models to think more before operating."],
        [
            "--repl",
            "",
            "Start a REPL session after executing the prompt or the script.",
        ],
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
    p.add_argument("--think", action="store_true")
    p.add_argument("--model", "-m", type=str, default=None)
    p.add_argument("--repl", action="store_true")
    p.add_argument("PROMPT_OR_FILE", nargs="?", default=None)
    p.add_argument("ARGS", nargs=argparse.REMAINDER)

    try:
        args = p.parse_args()
    except argparse.ArgumentError as e:
        rich.print(f"[bold red]Error:[/bold red] {str(e)}", file=sys.stderr)
        print_help()
        sys.exit(1)

    if args.help:
        print_help()
        sys.exit(0)

    CLI_OPTIONS.yes = args.yes
    CLI_OPTIONS.quiet = args.quiet
    CLI_OPTIONS.start_repl_after_prompt = args.repl

    if args.model:
        if args.think:
            CONFIG.think_model = args.model
        else:
            CONFIG.model = args.model

    if args.think:
        CLI_OPTIONS.think = True

    prompt = args.PROMPT_OR_FILE.strip() if args.PROMPT_OR_FILE else None

    if prompt == "":
        prompt = None

    return prompt, (args.ARGS or [])


def main():
    # dotenv.load_dotenv()
    prompt, args = parse_args()

    if key := os.getenv("OPENROUTER_API_KEY"):
        CONFIG.api_key = key
    if CONFIG.api_key is None:
        rich.print(
            f"[bold red]Error:[/bold red] [red]OpenRouter API key not found.\nPlease set the OPENROUTER_API_KEY environment variable or add it to your config file: {USER_CONFIG_PATH}.[/red]"
        )
        sys.exit(1)
    try:
        asyncio.run(start_session(prompt, args))
    except (KeyboardInterrupt, EOFError):
        rich.print("\n[red]Aborted.[/red]")
        sys.exit(1)
