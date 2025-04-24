import asyncio
from pathlib import Path
import sys
from agentia import (
    Agent,
    UserMessage,
    Event,
    ToolCallEvent,
    MessageStream,
    ChatCompletion,
    UserConsentEvent,
)
from agentia.plugins import PluginInitError
from neongrid.loading import Loading

from autosh.config import CLI_OPTIONS, CONFIG
import neongrid as ng
from .plugins import create_plugins
import rich
import platform
from rich.prompt import Confirm


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
        agent.history.add(self.__get_argv_message())
        completion = agent.chat_completion(prompt, stream=True)
        async for stream in completion:
            await self.__render_streamed_markdown(stream)
        sys.exit(0)

    def __get_argv_message(self):
        args = str(CLI_OPTIONS.args)
        if not CLI_OPTIONS.script:
            cmd = Path(sys.argv[0]).name
        else:
            cmd = CLI_OPTIONS.script.name
        return UserMessage(
            content=f"PROGRAM NAME: {cmd}\n\nCOMMAND LINE ARGS: {args}\n\nCWD: {str(Path.cwd())}",
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
        loading = self.__create_loading_indicator()
        CLI_OPTIONS.prompt = prompt
        self.agent.history.add(self.__get_argv_message())
        if CLI_OPTIONS.stdin_has_data():
            self.agent.history.add(
                UserMessage(
                    content="IMPORTANT: You are acting as an intermediate tool of a workflow. Input data is fed to you through piped stdin. Please use tools to read when necessary.",
                    role="user",
                )
            )
        if not sys.stdout.isatty():
            self.agent.history.add(
                UserMessage(
                    content="IMPORTANT: You are acting as an intermediate tool of a workflow. Your output should only contain the user expected output, nothing else. Don't ask user questions or print anything else since the user cannot see it.",
                    role="user",
                )
            )
        else:
            self.agent.history.add(
                UserMessage(
                    content="IMPORTANT: This is a one-off run, so don't ask user questions since the user cannot reply.",
                    role="user",
                )
            )
        completion = self.agent.chat_completion(prompt, stream=True, events=True)
        await self.__process_completion(completion, loading)

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

    async def __process_event(self, e: Event):
        if isinstance(e, UserConsentEvent):
            e.response = await self.__confirm(e.message)
        if isinstance(e, ToolCallEvent) and e.result is None:
            if banner := (e.metadata or {}).get("banner"):
                banner(e.arguments)

    async def __confirm(self, message: str) -> bool:
        if CLI_OPTIONS.yes:
            return True
        result = Confirm.ask(
            f"[magenta]{message}[/magenta]", default=True, case_sensitive=False
        )
        if not CLI_OPTIONS.quiet:
            rich.print()
        return result

    async def __process_completion(
        self, completion: ChatCompletion[Event | MessageStream], loading: Loading
    ):
        async for stream in completion:
            await loading.finish()

            if isinstance(stream, Event):
                await self.__process_event(stream)
            else:
                print()
                await self.__render_streamed_markdown(stream)
                print()

            loading = self.__create_loading_indicator()

        await loading.finish()

    async def run_repl(self):
        while True:
            try:
                prompt = (
                    await ng.input("> ", sync=False, persist="/tmp/autosh-history")
                ).strip()
                if prompt in ["exit", "quit"]:
                    break
                if len(prompt) == 0:
                    continue
                loading = self.__create_loading_indicator()
                completion = self.agent.chat_completion(
                    prompt, stream=True, events=True
                )
                await self.__process_completion(completion, loading)
            except KeyboardInterrupt:
                break

    def __create_loading_indicator(self):
        return ng.loading.kana()

    async def __render_streamed_markdown(self, stream: MessageStream):
        if sys.stdout.isatty():
            await ng.stream.markdown(aiter(stream))
            return True
        else:
            async for chunk in stream:
                print(chunk, end="", flush=True)
