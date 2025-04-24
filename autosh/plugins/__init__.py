from typing import Any, Callable
import rich
from rich.prompt import Confirm
from rich.panel import Panel
from rich.console import RenderableType
from autosh.config import CLI_OPTIONS, CONFIG


def __print_simple_banner(tag: str, text: str | None = None, dim: str | None = None):
    if CLI_OPTIONS.quiet:
        return
    s = f"\n[bold on magenta] {tag} [/bold on magenta]"
    if text:
        s += f" [italic magenta]{text}[/italic magenta]"
    if dim:
        s += f" [italic dim]{dim}[/italic dim]"
    rich.print(s)


def simple_banner(
    tag: str | Callable[[Any], str],
    text: Callable[[Any], str] | None = None,
    dim: Callable[[Any], str] | None = None,
):
    return lambda x: __print_simple_banner(
        tag if isinstance(tag, str) else tag(x),
        text(x) if text else None,
        dim(x) if dim else None,
    )


def __print_code_preview_banner(
    title: str, content: RenderableType, short: str | None = None
):
    if CLI_OPTIONS.quiet:
        if short and not CLI_OPTIONS.yes:
            rich.print(f"\n[magenta]{short}[/magenta]\n")
        return
    panel = Panel.fit(content, title=f"[magenta]{title}[/magenta]", title_align="left")
    rich.print()
    rich.print(panel)
    rich.print()


def code_preview_banner(
    title: str | Callable[[Any], str],
    short: str | Callable[[Any], str],
    content: Callable[[Any], RenderableType],
):
    return lambda x: __print_code_preview_banner(
        title=title if isinstance(title, str) else title(x),
        content=content(x),
        short=short if isinstance(short, str) else short(x),
    )


def code_result_panel(
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
