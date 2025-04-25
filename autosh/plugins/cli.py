import os
import sys
from typing import Annotated
from agentia import Plugin, tool, UserConsentEvent
import rich
import subprocess
from enum import StrEnum

from autosh.config import CLI_OPTIONS

from . import code_result_panel, Banner


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
        stderr: Annotated[bool, "Whether to print the text to stderr"] = False,
        end: Annotated[str, "The text to print at the end"] = "\n",
    ):
        """
        Print an important message to the terminal. NOTE: Important message ONLY! Don't use it when you want to say something to the user.
        """
        if color:
            text = f"[{color}]{text}[/{color}]"
        if bold:
            text = f"[bold]{text}[/bold]"
        if italic:
            text = f"[italic]{text}[/italic]"
        rich.print(text, file=sys.stderr if stderr else sys.stdout, end=end)
        return "DONE. You can continue and no need to repeat the text"

    @tool(metadata={"banner": Banner("CWD", text_key="path")})
    def chdir(self, path: Annotated[str, "The path to the new working directory"]):
        """
        Changes the current working directory of the terminal to another directory.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path `{path}` does not exist.")
        os.chdir(path)
        return f"DONE"

    @tool(metadata={"banner": Banner("GET ARGV")})
    def get_argv(self):
        """
        Get the command line arguments.
        """
        if not CLI_OPTIONS.script:
            return CLI_OPTIONS.args
        return {
            "script": str(CLI_OPTIONS.script),
            "args": CLI_OPTIONS.args,
        }

    @tool(metadata={"banner": Banner("GET ENV", text_key="key")})
    def get_env(self, key: Annotated[str, "The environment variable to get"]):
        """
        Get an environment variable.
        """
        if key not in os.environ:
            raise KeyError(f"Environment variable `{key}` does not exist.")
        return os.environ[key]

    @tool(metadata={"banner": Banner("GET ALL ENVS")})
    def get_all_envs(self):
        """
        Get all environment variables.
        """
        envs = {}
        for key, value in os.environ.items():
            envs[key] = value
        return {"envs": envs}

    @tool(
        metadata={
            "banner": Banner(
                title=lambda a: "SET ENV" if a.get("value") else "DEL ENV",
                text=lambda a: (
                    f"{a.get("key", "")} = {a.get("value", "")}"
                    if a.get("value")
                    else a.get("key", "")
                ),
            ),
        }
    )
    def update_env(
        self,
        key: Annotated[str, "The environment variable to set"],
        value: Annotated[
            str | None,
            "The value to set the environment variable to, or None to delete it",
        ],
    ):
        """
        Set or delete an environment variable.
        """
        if value is None:
            if key in os.environ:
                del os.environ[key]
        else:
            os.environ[key] = value
        return f"DONE"

    @tool(metadata={"banner": Banner("READ", text_key="path")})
    def read(
        self,
        path: Annotated[str, "The path to the file to read"],
    ):
        """
        Read a file and print its content.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"File `{path}` does not exist.")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Path `{path}` is not a file.")
        with open(path, "r") as f:
            content = f.read()
        return content

    @tool(
        metadata={
            "banner": Banner(
                title=lambda a: "WRITE" if not a.get("append") else "APPEND",
                text=lambda a: f"{a.get("path", "")} ({len(a.get('content', ''))} bytes)",
            ),
        }
    )
    def write(
        self,
        path: Annotated[str, "The path to the file to write"],
        content: Annotated[str, "The content to write to the file"],
        create: Annotated[
            bool, "Whether to create the file if it does not exist"
        ] = True,
        append: Annotated[bool, "Whether to append to the file if it exists"] = False,
    ):
        """
        Write or append text content to a file.
        """
        if not create and not os.path.exists(path):
            raise FileNotFoundError(f"File `{path}` does not exist.")
        if not create and not os.path.isfile(path):
            raise FileNotFoundError(f"Path `{path}` is not a file.")
        if path == str(CLI_OPTIONS.script):
            raise FileExistsError(
                f"No, you cannot overwrite the script file `{path}`. You're likely writing to it by mistake."
            )
        if not (yield UserConsentEvent("Write file?")):
            return {"error": "The user declined the write operation."}
        flag = "a" if append else "w"
        if create:
            flag += "+"
        with open(path, flag) as f:
            f.write(content)
        return "DONE. You can continue and no need to repeat the text"

    @tool
    def stdin_readline(
        self,
        prompt: Annotated[
            str | None, "The optional prompt to display before reading from stdin"
        ] = None,
    ):
        """
        Read a line from stdin.
        """
        if not sys.stdin.isatty():
            raise RuntimeError("stdin is not a terminal.")
        return input(prompt)

    @tool
    def stdin_readall(self):
        """
        Read all from stdin until EOF.
        """
        if sys.stdin.isatty():
            raise RuntimeError("No piped input. stdin is a terminal.")
        if not CLI_OPTIONS.quiet:
            rich.print("[bold magenta]READ ALL STDIN[/bold magenta]\n")
        if CLI_OPTIONS.stdin_is_script:
            raise RuntimeError("No piped input from stdin")
        return sys.stdin.read()

    @tool(
        metadata={
            "banner": Banner(
                title="Run Command",
                text_key="command",
                code=lambda a: f"[magenta][bold]➜[/bold] [italic]{a.get("command", "")}[/italic][/magenta]\n\n[dim]{a.get("explanation", "")}[/dim]",
                user_consent=True,
            )
        }
    )
    def exec(
        self,
        command: Annotated[
            str,
            "The one-liner bash command to execute. This will be directly sent to `bash -c ...` so be careful with the quotes escaping!",
        ],
        explanation: Annotated[
            str,
            "Explain what this command does, and what are you going to use it for.",
        ],
    ):
        """
        Run a one-liner bash command
        """

        def run():
            cmd = ["bash", "-c", command]
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Ask for confirmation
        if not (yield UserConsentEvent("Execute this command?")):
            return {"error": "The user declined to execute the command."}

        # Execute the command
        proc_result = run()

        # Print the result
        if not CLI_OPTIONS.quiet:
            out = proc_result.stdout.decode("utf-8")
            err = proc_result.stderr.decode("utf-8")
            if not out and not err:
                title = "[green][bold]✔[/bold] Command Finished[/green]"
            else:
                if proc_result.returncode != 0:
                    title = f"[red][bold]✘[/bold] Command Failed [{proc_result.returncode}][/red]"
                else:
                    title = "[green][bold]✔[/bold] Command Finished[/green]"
            code_result_panel(title, out, err)

        result = {
            "stdout": proc_result.stdout.decode("utf-8"),
            "stderr": proc_result.stderr.decode("utf-8"),
            "returncode": proc_result.returncode,
            "success": proc_result.returncode == 0,
        }
        return result

    @tool(metadata={"banner": Banner("EXIT")})
    def exit(
        self,
        exitcode: Annotated[int, "The exit code of this shell session"] = 0,
        reason: Annotated[str | None, "The reason for exiting"] = None,
    ):
        """
        Exit the current shell session with an optional exit code.
        """
        if reason and exitcode != 0:
            rich.print(f"\n[bold red]ABORT: {reason}[/bold red]")
        sys.exit(exitcode)
        return f"EXITED with code {exitcode}"
