import os
import sys
from typing import Annotated
from agentia.plugins import Plugin, tool
import rich
import subprocess
from rich.prompt import Confirm
from rich.panel import Panel


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
    ):
        """
        Run a one-liner bash command
        """
        rich.print(
            f"[bold magenta]➜[/bold magenta] [italic magenta]{command}[/italic magenta]"
        )
        # User confirmation before executing
        if not Confirm.ask(
            "[magenta]Execute this command?[/magenta]",
            default=True,
            case_sensitive=False,
        ):
            return {
                "error": "The user declined to execute the command.",
            }
        proc_result = subprocess.run(
            ["bash", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # shell=True,
        )
        text = f"[bold]$[/bold] {command}\n\n"
        stdout = proc_result.stdout.decode("utf-8").strip()
        stderr = proc_result.stderr.decode("utf-8").strip()
        if stdout:
            text += stdout + "\n"
        if stderr:
            if stdout:
                text += "\n---\n"
            text += stderr + "\n"

        panel = Panel.fit(text, title=f"Run Command", title_align="left", style="dim")
        rich.print(panel)
        # console = rich.console.Console()
        # if proc_result.stdout:
        #     console.print(proc_result.stdout.decode("utf-8"), style="dim")
        # if proc_result.stderr:
        #     console.print(proc_result.stderr.decode("utf-8"), style="dim")
        # print("Exec 3")
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
