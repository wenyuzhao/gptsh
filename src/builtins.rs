pub fn is_built_in_command(command: &str) -> bool {
    let first = command.split_whitespace().next().unwrap_or("");
    match first {
        "exit" => true,
        "cd" => true,
        _ => false,
    }
}

pub fn execute_built_in_command(command: &str) -> anyhow::Result<()> {
    let first = command.split_whitespace().next().unwrap_or("");
    match first {
        "exit" => std::process::exit(0),
        "cd" => {
            let args: Vec<&str> = command.split_whitespace().collect();
            if args.len() < 2 {
                anyhow::bail!("cd: missing argument");
            }
            let path = args[1];
            match std::env::set_current_dir(path) {
                Ok(_) => {},
                Err(e) => anyhow::bail!("cd: {}", e),
            }
            Ok(())
        }
        _ => anyhow::bail!("Command not found: {}", command),
    }
}
