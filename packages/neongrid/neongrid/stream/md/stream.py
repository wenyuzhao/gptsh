from typing import AsyncIterator


class TextStream:
    def __init__(self, gen: AsyncIterator[str]):
        self.__stream = gen
        self.__buf: str = ""
        self.__eof = False

    async def init(self):
        try:
            self.__buf = await anext(self.__stream)
        except StopAsyncIteration:
            self.__eof = True

    async def __ensure_length(self, n: int):
        while (not self.__eof) and len(self.__buf) < n:
            try:
                self.__buf += await anext(self.__stream)
            except StopAsyncIteration:
                self.__eof = True

    def peek(self):
        c = self.__buf[0] if len(self.__buf) > 0 else None
        return c

    async def check(self, s: str, eof: bool | None = None) -> bool:
        if len(s) == 0:
            return True
        await self.__ensure_length(len(s) + 1)
        if len(self.__buf) < len(s):
            return False
        matched = self.__buf[0 : len(s)] == s
        if matched:
            if eof is not None:
                if eof:
                    # return false if there is more data
                    if len(self.__buf) > len(s):
                        return False
                else:
                    # return false if there is no more data
                    if len(self.__buf) == len(s):
                        return False
        return matched

    async def consume(self, n: int = 1):
        await self.__ensure_length(n)
        if len(self.__buf) < n:
            return None
        s = self.__buf[:n]
        self.__buf = self.__buf[n:]
        await self.__ensure_length(1)
        return s

    async def unordered_list_label(self) -> bool:
        if self.__eof:
            return False
        await self.__ensure_length(2)
        buf = self.__buf
        if len(buf) < 2:
            return False
        if buf[0] in ["-", "+", "*"] and buf[1] == " ":
            return True
        return False

    async def ordered_list_label(self) -> bool:
        if self.__eof:
            return False
        await self.__ensure_length(5)
        buf = self.__buf
        # \d+\.
        if len(buf) == 0:
            return False
        if not buf[0].isnumeric():
            return False
        has_dot = False
        for i in range(1, 5):
            if i >= len(buf):
                return False
            c = buf[i]
            if c == ".":
                if has_dot:
                    return False
                has_dot = True
                continue
            if c == " ":
                if has_dot:
                    return True
                return False
            if c.isnumeric():
                continue
        return False

    async def non_paragraph_block_start(self):
        await self.__ensure_length(3)
        buf = self.__buf[:3] if len(self.__buf) >= 3 else self.__buf
        if buf.startswith("```"):
            return True
        if buf.startswith("---"):
            return True
        if buf.startswith("> "):
            return True
        if await self.ordered_list_label():
            return True
        if await self.unordered_list_label():
            return True
        return False
