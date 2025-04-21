from agentia.plugins import tool, Plugin
from typing import Annotated
import traceback
from rich.syntax import Syntax
from rich.console import group
from contextlib import redirect_stdout, redirect_stderr
import io
from . import confirm, cmd_result_panel, cmd_preview_panel


class CodePlugin(Plugin):
    @tool
    def execute(
        self,
        python_code: Annotated[str, "The python code to run."],
        explanation: Annotated[
            str, "Explain what this code does, and what are you going to use it for."
        ],
    ):
        """
        Execute python code and return the result.
        The python code must be a valid python source file that accepts no inputs.
        Print results to stdout or stderr.
        """

        @group()
        def code_with_explanation():
            yield Syntax(python_code.strip(), "python")
            yield "\n[dim]───[/dim]\n"
            yield f"[dim]{explanation}[/dim]"

        cmd_preview_panel(
            title="Run Python",
            content=code_with_explanation(),
            short=f"[bold]RUN[/bold] [italic]Python Code[/italic]",
        )

        if not confirm("Execute this code?"):
            return {"error": "The user declined to execute the command."}

        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out):
            with redirect_stderr(err):
                try:
                    exec(python_code, globals())
                    o = out.getvalue()
                    e = err.getvalue()
                    title = "[green][bold]✔[/bold] Finished[/green]"
                    result = {
                        "stdout": o,
                        "stderr": e,
                        "success": True,
                    }
                except Exception as ex:
                    o = out.getvalue()
                    e = err.getvalue()
                    title = "[red][bold]✘[/bold] Failed [/red]"
                    result = {
                        "stdout": o,
                        "stderr": e,
                        "success": False,
                        "error": str(ex),
                        "traceback": repr(traceback.format_exc()),
                    }

        cmd_result_panel(title, o, e)
        return result
