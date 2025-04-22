# `autosh` - The AI-powered, noob-friendly interactive shell

# Getting Started

## Install

```bash
uv tool install autosh
```

## Usage

As an interactive shell: `ash` (alternatively, `autosh`)

Execute a single prompt: `ash "list current directory"`

Process piped data:
* `cat README.md | ash -y "summarise"`
* `cat in.csv | ash -y -q "double the first numeric column" > out.csv`

## Scripting

Write AI-powered shell scripts in Markdown using natural language!

Example script ([simple.a.md](examples/simple.a.md)):

```markdown
#!/usr/bin/env ash

# This is a simple file manipulation script

First, please display a welcome message:)

Write "Hello, world" to _test.log
```

* Run the script: `ash simple.a.md` or `chmod +x simple.a.md && simple.a.md`
* Auto generate help messages:

    ```console
    $ ash simple.a.md -h

    Usage: simple.a.md [OPTIONS]

    This is a simple file manipulation script that writes "Hello, world" to a log file named _x.log.

    Options:

    • -h, --help     Show this message and exit.
    ```

## Plugins

`autosh` is equipped with several plugins to expand its potential:

* `ash "Create a directory "my-news", list the latest news, for each news, put the summary in a separate markdown file in this directory"`

# TODO

- [ ] Image input, generation, and editing
- [ ] RAG for non-text files
- [ ] Plugin system
- [ ] MCP support
- [ ] A better input widget with history and auto completion
