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
    /// The prompt or command to run.
    #[arg(last = true, allow_hyphen_values = true)]
    prompt: Vec<String>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    // Create session
    let mut session = session::ShellSession::new()?;
    // Run the session
    if let Some(ref _script) = args.script_file {
        unimplemented!("Script file support is not yet implemented");
    } else if args.prompt.len() > 0 {
        let prompt = args.prompt.join(" ");
        session.run_single_prompt(&prompt).await?;
    } else {
        session.run_repl().await?;
    }
    Ok(())
}
