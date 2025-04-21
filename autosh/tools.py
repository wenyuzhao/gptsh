import os
import sys
from typing import Annotated
from agentia.plugins import Plugin, tool
import rich
import subprocess
from rich.prompt import Confirm
from rich.panel import Panel
from enum import StrEnum

from autosh.config import CLI_OPTIONS


class Color(StrEnum):
    black = "black"
    red = "red"
    green = "green"
    yellow = "yellow"
    blue = "blue"
    magenta = "magenta"
    cyan = "cyan"
    white = "white"
    bright_black = "bright_black"
    bright_red = "bright_red"
    bright_green = "bright_green"
    bright_yellow = "bright_yellow"
    bright_blue = "bright_blue"
    bright_magenta = "bright_magenta"
    bright_cyan = "bright_cyan"
    bright_white = "bright_white"
    dim = "dim"


class CLIPlugin(Plugin):
    EXIT_CODE = 0

    @tool
    def print(
        self,
        text: Annotated[
            str,
            "The text to print. Can be markdown or using python-rich's markup syntax.",
        ],
        color: Annotated[Color | None, "The color of the text"] = None,
        bold: Annotated[bool, "Whether to print the text in bold"] = False,
        italic: Annotated[bool, "Whether to print the text in italic"] = False,
    ):
        """
        Print an important message to the terminal. NOTE: Don't use it when you want to say something to the user.
        """
        if color:
            text = f"[{color}]{text}[/{color}]"
        if bold:
            text = f"[bold]{text}[/bold]"
        if italic:
            text = f"[italic]{text}[/italic]"
        rich.print(text)
        return "DONE. You can continue and no need to repeat the text"

    @tool
    def chdir(self, path: Annotated[str, "The path to the new working directory"]):
        """
        Changes the current working directory of the terminal to another directory.
        """
        rich.print(
            f"[bold magenta]CWD[/bold magenta] [italic magenta]{path}[/italic magenta]"
        )
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path `{path}` does not exist.")
        os.chdir(path)

    @tool
    def exec(
        self,
        command: Annotated[
            str,
            "The one-liner bash command to execute. This will be directly sent to `bash -c ...` so be careful with the quotes escaping!",
        ],
        explanation: Annotated[
            str,
            "Explain what this command does, and how are you going to use it.",
        ],
    ):
        """
        Run a one-liner bash command
        """
        # rich.print(
        #     f"[bold magenta]➜[/bold magenta] [italic magenta]{command}[/italic magenta]"
        # )
        # rich.print(f"[dim]{explanation}[/dim]")

        def confirm():
            if CLI_OPTIONS.yes:
                return True
            if not CLI_OPTIONS.quiet:
                rich.print()
            return Confirm.ask(
                "[magenta]Execute this command?[/magenta]",
                default=True,
                case_sensitive=False,
            )

        def run():
            cmd = ["bash", "-c", command]
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        decline_error = {"error": "The user declined to execute the command."}

        # Print the command and explanation
        if CLI_OPTIONS.quiet and not CLI_OPTIONS.yes:
            text = f"[magenta][bold]➜[/bold] [italic]{command}[/italic][/magenta]"
            rich.print(text)
        elif CLI_OPTIONS.quiet:
            pass
        else:
            text = f"[magenta][bold]➜[/bold] [italic]{command}[/italic][/magenta]\n\n[dim]{explanation}[/dim]"
            panel = Panel.fit(
                text, title=f"[magenta]Run Command[/magenta]", title_align="left"
            )
            rich.print(panel)

        # Ask for confirmation
        if not confirm():
            return decline_error

        # Execute the command
        proc_result = run()

        # Print the result
        if not CLI_OPTIONS.quiet:
            text = f"[bold]➜ {command}[/bold]\n\n"
            out = proc_result.stdout.decode("utf-8").strip()
            err = proc_result.stderr.decode("utf-8").strip()
            text += out if out else ""
            text += (("\n---\n" if out else "") + err + "\n") if err else ""
            rich.print()
            if proc_result.returncode != 0:
                title = f"[bold red][bold]✘[/bold] Command Failed [{proc_result.returncode}][/bold red]"
            else:
                title = "[green][bold]✔[/bold] Command Finished[/green]"
            panel = Panel.fit(text, title=title, title_align="left", style="dim")
            rich.print(panel)
            rich.print()

        result = {
            "stdout": proc_result.stdout.decode("utf-8"),
            "stderr": proc_result.stderr.decode("utf-8"),
            "returncode": proc_result.returncode,
            "success": proc_result.returncode == 0,
        }
        return result

    @tool
    def exit(self, exitcode: Annotated[int, "The exit code of this shell session"] = 0):
        """
        Exit the current shell session with an optional exit code.
        """
        rich.print(
            f"[bold magenta]EXIT[/bold magenta] [italic magenta]{exitcode}[/italic magenta]"
        )
        sys.exit(exitcode)
