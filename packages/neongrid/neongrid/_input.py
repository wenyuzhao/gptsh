from pathlib import Path
import sys
from types import FrameType
from neongrid.style import ESC, STYLE
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory, History, FileHistory

import inspect
from typing import Any, Awaitable, Literal, overload

import rich

from neongrid._print import printmd


class MyFileHistory(FileHistory):
    def __init__(self, filename: Path) -> None:
        super().__init__(filename)

    def store_string(self, string: str) -> None:
        super().store_string(string)
        # Only keep the last 1000 lines in the history file.
        if len(self._loaded_strings) > 1000:
            with open(self.filename, "r", encoding="utf-8") as f:
                lines = f.readlines()
                entries = []
                i = 0
                while i < len(lines):
                    line = lines[i]
                    if line.startswith("#"):
                        entries.append(line)
                    elif line.startswith("+"):
                        if len(entries) == 0:
                            entries.append(line)
                        else:
                            entries[-1] += line
                # keep last 1000 entries
                entries = entries[-1000:]
            with open(self.filename, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(entry)


def get_frame(frame: FrameType):
    # Adapted from: https://gist.github.com/lee-pai-long/d3004225e1847b84acb4fbba0c2aea91
    # module and packagename.
    module_info = inspect.getmodule(frame)
    if module_info:
        module_name = module_info.__name__
    else:
        module_name = "_"
    # class name.
    klass = "_"
    if "self" in frame.f_locals:
        klass = frame.f_locals["self"].__class__.__name__
    # method or function name.
    caller = "_"
    if frame.f_code.co_name != "<module>":  # top level usually
        caller = frame.f_code.co_name
    # call line.
    line = frame.f_lineno
    return f"{module_name},{klass},{caller},{line}"


def get_callsite():
    # Adapted from: https://gist.github.com/lee-pai-long/d3004225e1847b84acb4fbba0c2aea91
    skip = 1
    stack = inspect.stack()
    if len(stack) < skip + 1:
        return ""
    frames = stack[skip:]
    return ";".join([get_frame(frame[0]) for frame in frames])


HISTORY: dict[str, InMemoryHistory] = {}


def load_persistent_history(path: Path | str) -> History:
    path = Path(path) if isinstance(path, str) else path
    if not path.exists():
        path.touch()
    history = FileHistory(path)
    return history


@overload
def input(
    prompt: str | None = None,
    *,
    sync: Literal[True] = True,
    id: str | None = None,
    persist: Path | str | Literal[False] = False,
) -> str: ...


@overload
def input(
    prompt: str | None = None,
    *,
    sync: Literal[False],
    id: str | None = None,
    persist: Path | str | Literal[False] = False,
) -> Awaitable[str]: ...


def __get_prompt(prompt: str) -> Any:
    style = "bold"
    if c := STYLE.input_color:
        style += f" fg:ansi{c.name}"
    return [(style, prompt)]


def input(
    prompt: str | None = None,
    *,
    sync: bool = True,
    id: str | None = None,
    persist: Path | str | Literal[False] = False,
) -> Awaitable[str] | str:
    """
    Input function with fish-style history and auto-suggestions.
    """
    if persist:
        history = load_persistent_history(persist)
    else:
        if id is None:
            id = get_callsite()
        if id not in HISTORY:
            HISTORY[id] = InMemoryHistory()
        history = HISTORY[id]
    session = PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
    )
    if prompt is not None and STYLE.input_color:
        prompt = [
            ("fg:" + STYLE.input_color.name, prompt),
        ]  # type: ignore
    if sync:
        return session.prompt(prompt)
    else:
        return session.prompt_async(prompt)
