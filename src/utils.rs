use std::{
    io::{self, IsTerminal, Write},
    path::PathBuf,
};

use colored::Colorize;
use crossterm::event::{self, Event, KeyCode, KeyEvent};

use crate::utils;

pub fn get_cwd_short_form() -> String {
    let cwd = std::env::current_dir().unwrap();
    let home_dir = home::home_dir().unwrap();
    let cwd = cwd.to_str().unwrap();
    let home_dir = home_dir.to_str().unwrap();
    let simplified_home_dir = if cwd.starts_with(home_dir) {
        cwd.replacen(home_dir, "~", 1)
    } else {
        cwd.to_string()
    };
    let simplified_home_dir = PathBuf::from(simplified_home_dir);
    let mut segments = vec![];
    let num_segments = simplified_home_dir.components().count();

    for (i, c) in simplified_home_dir.components().enumerate() {
        if i == num_segments - 1 {
            segments.push(c.as_os_str().to_str().unwrap().to_string());
        } else {
            segments.push(
                c.as_os_str()
                    .to_str()
                    .unwrap()
                    .chars()
                    .next()
                    .unwrap()
                    .to_string(),
            );
        }
    }

    let s = segments.join("/");
    if !s.starts_with('~') {
        format!("/{}", s)
    } else {
        s
    }
}

pub fn read_user_prompt() -> anyhow::Result<Option<String>> {
    // Print the prompt
    if is_terminal() {
        print!(
            "{}{} ",
            get_cwd_short_form().bold().on_blue().white(),
            "\u{e0b0}".blue()
        );
    }
    io::stdout().flush()?;
    let mut buffer = String::new();
    let size = io::stdin().read_line(&mut buffer)?;
    if size == 0 {
        return Ok(None);
    }
    Ok(Some(buffer))
}

pub fn wait_for_user_acknowledgement() -> bool {
    let s = format!("[{}] Confirm • [{}] Abort", "ENTER↵".green(), "^c".red())
        .white()
        .on_bright_black();
    print!("{}", &s);
    io::stdout().flush().unwrap();
    crossterm::terminal::enable_raw_mode().unwrap();
    let mut abort = false;
    while let Event::Key(KeyEvent {
        code, modifiers, ..
    }) = event::read().unwrap()
    {
        if code == KeyCode::Enter {
            break;
        } else if code == KeyCode::Char('c') && modifiers == event::KeyModifiers::CONTROL {
            abort = true;
            break;
        }
    }
    crossterm::terminal::disable_raw_mode().unwrap();
    let back = s.as_bytes().iter().map(|_| "\u{8}").collect::<String>();
    let ws = s.as_bytes().iter().map(|_| " ").collect::<String>();
    print!("{}{}{}", back, ws, back);
    io::stdout().flush().unwrap();
    if abort {
        println!("{}", "Aborted.".red());
    }
    !abort
}

/// Check if the inputs are coming from a terminal
pub fn is_terminal() -> bool {
    io::stdin().is_terminal()
}

pub fn print_banner(repl: bool) {
    if repl && utils::is_terminal() {
        println!(
            "🦄 Welcome to {}. The AI-powered noob-friendly interactive shell.",
            "gptsh".blue().bold()
        );
    }
    if whoami::username() == "root" {
        eprintln!(
            "🚨 {}",
            "WARNING: Running as root is dangerous and is not recommended!"
                .red()
                .bold()
        );
    }
}
