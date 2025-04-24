from typing import AsyncGenerator


async def markdown(stream: AsyncGenerator[str, None]):
    from .md.printer import StreamedMarkdownPrinter

    mp = StreamedMarkdownPrinter(stream)
    await mp.parse_doc()
