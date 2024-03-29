use clap::Parser;

mod builtins;
mod config;
mod session;
mod tools;
mod utils;

/// gptsh - The AI-powered, noob-friendly interactive shell.
#[derive(Parser, Debug)]
#[command(version = clap::crate_version!())]
struct Args {
    /// Path to a gptsh script file.
    script_file: Option<String>,
    /// Skip confirmation prompts before running bash commands.
    #[arg(short, long, default_value = "false")]
    yes: bool,
    /// Suppress all intermediate command output.
    #[arg(short, long, default_value = "false")]
    quiet: bool,
    /// The prompt or command to run.
    #[arg(last = true, allow_hyphen_values = true)]
    prompt: Vec<String>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    // Create session
    let mut session = session::ShellSession::new()?;
    session.yes = args.yes;
    if !utils::stdin_is_terminal() {
        session.yes = true;
    }
    session.quiet = args.quiet;
    // Run the session
    let repl = args.prompt.is_empty() && args.script_file.is_none();
    utils::print_banner(repl);
    if let Some(ref script_file) = args.script_file {
        session.run_script(script_file).await?;
    } else if !args.prompt.is_empty() {
        let prompt = args.prompt.join(" ");
        session.run_single_prompt(&prompt).await?;
    } else {
        session.run_repl().await?;
    }
    Ok(())
}
