use std::{
    io::{self, Write},
    path::PathBuf,
};

use colored::Colorize;
use crossterm::event::{self, Event, KeyCode, KeyEvent};

pub fn get_cwd_short_form() -> String {
    let cwd = std::env::current_dir().unwrap();
    let home_dir = home::home_dir().unwrap();
    let cwd = cwd.to_str().unwrap();
    let home_dir = home_dir.to_str().unwrap();
    let simplified_home_dir = if cwd.starts_with(home_dir) {
        let cwd = cwd.replacen(home_dir, "~", 1);
        cwd
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
    if !s.starts_with("~") {
        format!("/{}", s)
    } else {
        s
    }
}

pub fn read_user_prompt() -> anyhow::Result<String> {
    // Print the prompt
    print!(
        "{}{} ",
        get_cwd_short_form().bold().on_blue().white(),
        "\u{e0b0}".blue()
    );
    io::stdout().flush()?;
    let mut buffer = String::new();
    io::stdin().read_line(&mut buffer)?;
    Ok(buffer)
}

pub fn wait_for_user_acknowledgement() -> bool {
    let s = format!("[{}] Confirm • [{}] Abort", "ENTER↵".green(), "^x".red())
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
        } else if code == KeyCode::Char('x') && modifiers == event::KeyModifiers::CONTROL {
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