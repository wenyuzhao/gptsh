use chatgpt::{prelude::*, types::Role};
use clap::Parser;
use config::CONFIG;
use std::io::{self, Write};
use std::process::Command;

mod config;

/// GPT-Shell
#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    /// Name of the person to greet
    #[arg(short, long)]
    prompt: String,
}

fn get_prompt() -> anyhow::Result<String> {
    print!("> ");
    io::stdout().flush()?;
    let mut prompt = String::new();
    io::stdin().read_line(&mut prompt)?;
    Ok(prompt)
}

/// Sends message to a certain user. Returns `failure` if user does not exist.
///
/// * user - Name of the user
/// * message - Message to be sent
#[gpt_function]
async fn run_command(command: String) -> String {
    println!("RUN: {}", command);

    tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;

    let output = Command::new("bash")
        .args(["-c", &command])
        .output()
        .expect("Failed to execute command");

    let s = String::from_utf8(output.stdout).unwrap();
    println!("RESULT: {}", s);

    "done".to_string()
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let client = ChatGPT::new_with_config(
        &CONFIG.openai_api_key,
        ModelConfigurationBuilder::default()
            .function_validation(FunctionValidationStrategy::Strict)
            .build()
            .unwrap(),
    )?;
    loop {
        let prompt = get_prompt()?;

        // Sending a message and getting the completion
        let mut conv = client.new_conversation();

        conv.always_send_functions = true;

        // Adding the functions
        conv.add_function(run_command())?;
        conv.history.push(ChatMessage {
            role: Role::System,
            content: r#"
                You should act as a AI terminal shell.
                The user will send you prompts or descriptions of the tasks, instead of typing the bash commands directly.
                You should take the prompts and descriptions, and then generate the bash commands to execute the tasks.
            "#
            .to_string(),
            function_call: None,
        });

        // conv.send_message(message)
        let response = conv.send_message_functions(prompt).await?;

        println!("{:?}", conv.history);
        println!("{:?}", response);
    }
}
