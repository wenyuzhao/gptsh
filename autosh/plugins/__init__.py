import rich
from rich.prompt import Confirm
from rich.panel import Panel
from rich.console import RenderableType
from autosh.config import CLI_OPTIONS, CONFIG


def banner(tag: str, text: str | None = None, dim: str | None = None):
    if CLI_OPTIONS.quiet:
        return
    s = f"[bold magenta]{tag}[/bold magenta]"
    if text:
        s += f" [italic magenta]{text}[/italic magenta]"
    if dim:
        s += f" [italic dim]{dim}[/italic dim]"
    s += "\n"
    rich.print(s)


def confirm(message: str):
    if CLI_OPTIONS.yes:
        return True
    result = Confirm.ask(
        f"[magenta]{message}[/magenta]", default=True, case_sensitive=False
    )
    if not CLI_OPTIONS.quiet:
        rich.print()
    return result


def cmd_preview_panel(title: str, content: RenderableType, short: str | None = None):
    if CLI_OPTIONS.quiet and not CLI_OPTIONS.yes:
        if short:
            rich.print(f"[magenta]{short}[/magenta]\n")
        return
    panel = Panel.fit(content, title=f"[magenta]{title}[/magenta]", title_align="left")
    rich.print(panel)
    rich.print()


def cmd_result_panel(
    title: str,
    out: str | None = None,
    err: str | None = None,
):
    if CLI_OPTIONS.quiet:
        return
    if isinstance(out, str):
        out = out.strip()
    if isinstance(err, str):
        err = err.strip()
    if not out and not err:
        rich.print(title)
    else:
        text = out if out else ""
        text += (("\n---\n" if out else "") + err) if err else ""
        panel = Panel.fit(text, title=title, title_align="left", style="dim")
        rich.print(panel)
    if not CLI_OPTIONS.quiet:
        rich.print()


from . import calc
from . import clock
from . import code
from . import search
from . import web
from . import cli


def create_plugins():
    """Get all plugins in the autosh.plugins module."""
    cfgs = CONFIG.plugins
    plugins = []
    if cfgs.calc is not None:
        plugins.append(calc.CalculatorPlugin(cfgs.calc.model_dump()))
    if cfgs.cli is not None:
        plugins.append(cli.CLIPlugin(cfgs.cli.model_dump()))
    if cfgs.clock is not None:
        plugins.append(clock.ClockPlugin(cfgs.clock.model_dump()))
    if cfgs.code is not None:
        plugins.append(code.CodePlugin(cfgs.code.model_dump()))
    if cfgs.search is not None:
        plugins.append(search.SearchPlugin(cfgs.search.model_dump()))
    if cfgs.web is not None:
        plugins.append(web.WebPlugin(cfgs.web.model_dump()))
    return plugins
