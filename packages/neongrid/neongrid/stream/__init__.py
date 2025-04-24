from typing import AsyncIterator


async def markdown(stream: AsyncIterator[str]):
    from .md.printer import StreamedMarkdownPrinter

    mp = StreamedMarkdownPrinter(stream)
    await mp.parse_doc()
