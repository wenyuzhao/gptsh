from typing import AsyncGenerator

from autosh.md.printer import StreamedMarkdownPrinter


async def stream_md(stream: AsyncGenerator[str, None]):
    mp = StreamedMarkdownPrinter(stream)
    await mp.parse_doc()
