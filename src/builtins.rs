pub fn is_built_in_command(command: &str) -> bool {
    let words = shellwords::split(command).unwrap();
    match words[0].as_str() {
        "exit" => true,
        "cd" => words.len() == 2,
        _ => false,
    }
}

pub fn execute_built_in_command(command: &str) -> anyhow::Result<()> {
    let words = shellwords::split(command).unwrap();
    match words[0].as_str() {
        "exit" => std::process::exit(0),
        "cd" => {
            let args: Vec<&str> = words[1..].iter().map(|s| s.as_str()).collect();
            if args.len() < 2 {
                anyhow::bail!("cd: missing argument");
            }
            let path = args[1];
            match std::env::set_current_dir(path) {
                Ok(_) => {}
                Err(e) => anyhow::bail!("cd: {}", e),
            }
            Ok(())
        }
        _ => anyhow::bail!("Command not found: {}", command),
    }
}
