use clap::Parser;

mod config;
mod session;

/// GPT-Shell - A natural language based terminal shell powered by ChatGPT.
#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    /// The shell command or prompt.
    #[arg(short, long)]
    prompt: String,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let mut session = session::ShellSession::new()?;
    session.run().await?;
    Ok(())
}
