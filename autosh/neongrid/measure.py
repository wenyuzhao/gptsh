from dataclasses import dataclass
import os
import unicodedata


@dataclass
class Size:
    rows: int
    cols: int


def viewpoint():
    width = os.get_terminal_size().columns
    height = os.get_terminal_size().lines
    return Size(rows=int(height), cols=int(width))


def char_is_wide(c: str) -> bool:
    """
    Check if a character is wide (2 columns) or narrow (1 column).
    """
    return unicodedata.east_asian_width(c) in ("W", "F", "A")


def text_display_width(text: str) -> int:
    """
    Calculate the display width of a string.
    """
    return sum(2 if char_is_wide(c) else 1 for c in text)


def measure_text(text: str, wrap: int | None = None) -> tuple[Size, list[str]]:
    """
    Measure the width of a string in columns.
    """
    if wrap is not None:
        assert wrap > 0, "max_width must be greater than 0"
    limit = wrap or 1e10
    lines = text.splitlines()
    width = []
    rows = []
    for line in lines:
        if not line:
            continue
        width.append(0)
        rows.append("")
        for c in line:
            w = 2 if char_is_wide(c) else 1
            if wrap and width[-1] + w > limit:
                # start a new line
                width.append(w)
                rows.append(c)
            else:
                width[-1] += w
                rows[-1] += c
    return Size(len(width), max(width)), rows
