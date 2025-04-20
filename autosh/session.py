import sys
from agentia import Agent
from agentia.chat_completion import MessageStream

from autosh.md import stream_md
from .tools import CLIPlugin
import rich


INSTRUCTIONS = """
You are now acting as a AI-powered terminal shell, operating on the user's real computer.
The user will send you questions, prompts, or descriptions of the tasks.
You should take the prompts, and either answer the user's questions, or fullfill the tasks.
When necessary, generate the system commands, and execute them to fullfill the tasks.
Ensure you are escaping the quotes, newlines, and other special characters properly in the commands.
The system command output are displayed to the user directly, so don't simply repeat the output twice in your response.
Don't do anything else that the user doesn't ask for, or not relevant to the tasks.
Your responses should be as clear and concise as possible.

Apart from a terminal shell, when necessary, you also need to act as a normal ChatGPT to fullfill any generic tasks that the user asks you to do.
Don't refuse to do anything that the user asks you to do, unless it's illegal, or violates the user's privacy.

You may use markdown to format your responses.
"""


class Session:
    def __init__(self):
        self.agent = Agent(
            model="openai/gpt-4.1", instructions=INSTRUCTIONS, tools=[CLIPlugin()]
        )

    async def exec_one(self, prompt: str):
        completion = self.agent.chat_completion(prompt, stream=True)
        async for stream in completion:
            await self.__render_streamed_markdown(stream)

    async def run_repl(self):
        console = rich.console.Console()
        while True:
            try:
                prompt = console.input("[bold]>[/bold] ").strip()
                if prompt in ["exit", "quit"]:
                    break
                if len(prompt) == 0:
                    continue
                completion = self.agent.chat_completion(prompt, stream=True)
                async for stream in completion:
                    await self.__render_streamed_markdown(stream)
            except KeyboardInterrupt:
                break

    async def __render_streamed_markdown(self, stream: MessageStream):
        if sys.stdout.isatty():
            # buffer first few chars so we don't need to launch glow if there is no output
            chunks = aiter(stream)
            buf = ""
            while len(buf) < 8:
                try:
                    buf += await anext(chunks)
                except StopAsyncIteration:
                    if len(buf) == 0:
                        return
                    break

            async def gen():
                if buf:
                    yield buf
                while True:
                    try:
                        s = await anext(chunks)
                        for c in s:
                            yield c
                    except StopAsyncIteration:
                        break

            await stream_md(gen())
        else:
            async for chunk in stream:
                print(chunk, end="", flush=True)
