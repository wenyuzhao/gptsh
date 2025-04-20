from typing import Annotated
import typer
import asyncio
import dotenv
from .session import Session
import sys


app = typer.Typer(pretty_exceptions_show_locals=False)


async def async_run(prompt: str | None):
    session = Session()
    if prompt and sys.stdin.isatty():
        # No piped stdin, just run the prompt
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
def run(prompt: Annotated[str | None, typer.Argument()] = None):
    dotenv.load_dotenv()
    asyncio.run(async_run(prompt))


def main():
    app()
