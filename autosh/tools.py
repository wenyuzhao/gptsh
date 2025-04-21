import os
import sys
from typing import Annotated
from agentia.plugins import Plugin, tool
import rich
import subprocess
from rich.prompt import Confirm
from rich.panel import Panel
from rich.live import Live

from autosh.config import CONFIG


class CLIPlugin(Plugin):
    EXIT_CODE = 0

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
            if CONFIG.yes:
                return True
            return Confirm.ask(
                "\n[magenta]Execute this command?[/magenta]",
                default=True,
                case_sensitive=False,
            )

        def run():
            cmd = ["bash", "-c", command]
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        decline_error = {"error": "The user declined to execute the command."}

        # Print the command and explanation
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
