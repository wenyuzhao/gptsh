from pathlib import Path
import sys
from agentia import Agent
from agentia.chat_completion import MessageStream
from agentia.message import UserMessage
from agentia.plugins import PluginInitError

from autosh.config import CLI_OPTIONS, CONFIG
from autosh.md import stream_md
from .plugins import create_plugins
import rich
import platform


INSTRUCTIONS = f"""
You are now acting as a AI-powered terminal shell, operating on the user's real computer.

The user will send you questions, prompts, or descriptions of the tasks.
You should take the prompts, and either answer the user's questions, or fullfill the tasks.
When necessary, generate the system commands, and execute them to fullfill the tasks.

Don't do anything else that the user doesn't ask for, or not relevant to the tasks.
The system command output are displayed to the user directly, so don't repeat the output in your response.
Just respond with the text if you want to simply print something to the terminal, no need to use `echo` or `print`.

If the prompt mentions it requires some arguments/options/flags, look for then in the command line arguments list and use them to complete the tasks.

You may use markdown to format your responses.

YOUR HOST OS INFO: {platform.platform()}
"""


class Session:
    def __init__(self):
        self.agent = Agent(
            model=CONFIG.model if not CLI_OPTIONS.think else CONFIG.think_model,
            api_key=CONFIG.api_key,
            instructions=INSTRUCTIONS,
            tools=create_plugins(),
        )

    async def init(self):
        try:
            await self.agent.init()
        except PluginInitError as e:
            rich.print(
                f"[bold red]Error:[/bold red] [red]Plugin [bold italic]{e.plugin}[/bold italic] failed to initialize: {str(e.original)}[/red]"
            )
            sys.exit(1)

    def _exit_with_error(self, msg: str):
        rich.print(f"[bold red]Error:[/bold red] [red]{msg}")
        sys.exit(1)

    async def _print_help_and_exit(self, prompt: str):
        agent = Agent(
            model="openai/gpt-4o-mini",
            api_key=CONFIG.api_key,
            instructions=f"""
            This is a CLI program logic written in natural language.
            Please help me to generate the CLI --help message for this CLI app.
            Just output the help message, no need to add any other text.

            RESPONSE FORMAT:

            **Usage:** ...

            The description of the program.

            **Options:**

                * -f, --foo     Description of foo
                * -b, --bar     Description of bar
                * --baz         Description of baz
                ...
                * -h, --help     Show this message and exit.
            """,
        )
        agent.history.add(self._get_argv_message())
        completion = agent.chat_completion(prompt, stream=True)
        async for stream in completion:
            await self.__render_streamed_markdown(stream)
        sys.exit(0)

    def _get_argv_message(self):
        args = str(CLI_OPTIONS.args)
        if not CLI_OPTIONS.script:
            cmd = "PROMPT"
        else:
            cmd = CLI_OPTIONS.script.name
        return UserMessage(
            content=f"PROGRAM NAME: {cmd}\n\nCOMMAND LINE ARGS: {args}",
            role="user",
        )

    async def exec_prompt(self, prompt: str):
        # Clean up the prompt
        if prompt is not None:
            prompt = prompt.strip()
            if not prompt:
                sys.exit(0)
        # skip shebang line
        if prompt.startswith("#!"):
            prompt = prompt.split("\n", 1)[1]
        if len(CLI_OPTIONS.args) == 1 and (
            CLI_OPTIONS.args[0] == "-h" or CLI_OPTIONS.args[0] == "--help"
        ):
            await self._print_help_and_exit(prompt)
        # Execute the prompt
        CLI_OPTIONS.prompt = prompt
        self.agent.history.add(self._get_argv_message())
        if CLI_OPTIONS.stdin_has_data():
            self.agent.history.add(
                UserMessage(
                    content="IMPORTANT: The user is using piped stdin to feed additional data to you. Please use tools to read when necessary.",
                    role="user",
                )
            )
        completion = self.agent.chat_completion(prompt, stream=True)
        async for stream in completion:
            if await self.__render_streamed_markdown(stream):
                print()

    async def exec_from_stdin(self):
        if sys.stdin.isatty():
            self._exit_with_error("No prompt is piped to stdin.")
        prompt = sys.stdin.read()
        if not prompt:
            sys.exit(0)
        CLI_OPTIONS.stdin_is_script = True
        await self.exec_prompt(prompt)

    async def exec_script(self, script: Path):
        CLI_OPTIONS.script = script
        with open(script, "r") as f:
            prompt = f.read()
        await self.exec_prompt(prompt)

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
                    if await self.__render_streamed_markdown(stream):
                        print()
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
                        return False
                    break

            content = {"v": ""}

            async def gen():
                content["v"] = buf
                if buf:
                    yield buf
                while True:
                    try:
                        s = await anext(chunks)
                        content["v"] += s
                        for c in s:
                            yield c
                    except StopAsyncIteration:
                        break

            await stream_md(gen())
            return True
        else:
            has_content = False
            async for chunk in stream:
                if chunk == "":
                    continue
                has_content = True
                print(chunk, end="", flush=True)
            return has_content
