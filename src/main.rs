use clap::Parser;

mod builtins;
mod config;
mod session;
mod utils;

/// GPT-Shell - A natural language based terminal shell powered by ChatGPT.
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
    session.quiet = args.quiet;
    // Run the session
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
