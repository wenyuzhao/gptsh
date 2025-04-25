from dataclasses import dataclass
import sys
from typing import Any, Callable
import rich
from rich.panel import Panel
from rich.console import RenderableType
from autosh.config import CLI_OPTIONS, CONFIG


@dataclass
class Banner:
    title: str | Callable[[Any], str]

    text: str | Callable[[Any], str] | None = None

    text_key: str | None = None

    code: Callable[[Any], RenderableType] | None = None
    """
    Turn the banner into a code block
    """

    user_consent: bool = False

    def __get_text(self, args: Any):
        if self.text:
            return self.text(args) if callable(self.text) else self.text
        elif self.text_key:
            return args.get(self.text_key)
        return None

    def __print_simple_banner(self, args: Any):
        title = self.title(args) if callable(self.title) else self.title
        if not sys.stdout.isatty():
            s = f"[TOOL] {title}"
            if text := self.__get_text(args):
                s += f" {text}"
            print(s)
        else:
            s = f"[bold on magenta] {title} [/bold on magenta]"
            if text := self.__get_text(args):
                s += f" [italic dim]{text}[/italic dim]"
            rich.print(s)

    def render(self, args: Any, prefix_newline: bool = True) -> bool:
        if CLI_OPTIONS.quiet and not (self.user_consent and not CLI_OPTIONS.yes):
            return False
        if prefix_newline:
            print()
        if self.code:
            code = self.code(args)
            if CLI_OPTIONS.quiet and self.user_consent and not CLI_OPTIONS.yes:
                self.__print_simple_banner(args)
                return True
            panel = Panel.fit(
                code, title=f"[magenta]{self.title}[/magenta]", title_align="left"
            )
            rich.print(panel)
        else:
            self.__print_simple_banner(args)
        return True


def code_result_panel(
    title: str,
    out: str | None = None,
    err: str | None = None,
):
    if CLI_OPTIONS.quiet:
        return
    print()
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
