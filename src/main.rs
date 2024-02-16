use clap::Parser;

mod config;
mod session;

/// GPT-Shell - A natural language based terminal shell powered by ChatGPT.
#[derive(Parser, Debug)]
#[command(version, about, long_about = None )]
struct Args {
    /// Path to a gptsh script file.
    script_file: Option<String>,
    /// The prompt or command string.
    #[arg(short, long)]
    prompt: Option<String>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    println!("{:?}", args);
    // Create session
    let mut session = session::ShellSession::new()?;
    // Run the session
    if let Some(ref _script) = args.script_file {
        unimplemented!("Script file support is not yet implemented");
    } else if let Some(ref prompt) = args.prompt {
        session.run_single_prompt(&prompt).await?;
    } else {
        session.run_repl().await?;
    }
    Ok(())
}
