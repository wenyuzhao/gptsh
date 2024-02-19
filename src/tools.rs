use std::{
    io::{self, BufRead, BufReader},
    process::Stdio,
    sync::atomic::{AtomicBool, Ordering},
};

use async_openai::types::{
    ChatCompletionTool, ChatCompletionToolArgs, ChatCompletionToolType, FunctionObjectArgs,
};
use colored::Colorize;
use once_cell::sync::Lazy;
use serde_json::{json, Map, Value};

use crate::{builtins, utils};

pub struct GPTFunction {
    pub name: &'static str,
    pub desc: &'static str,
    pub params: Vec<Param>,
    pub handler: Box<dyn Fn(Value) -> Result<String, ToolError> + Sync + Send>,
}

impl GPTFunction {
    fn get_info(&self) -> anyhow::Result<ChatCompletionTool> {
        let param_props = self
            .params
            .iter()
            .map(|param| {
                let mut props = Map::new();
                props.insert("type".to_string(), json!(param.ty));
                props.insert("description".to_string(), json!(param.desc));
                (param.name.to_string(), json!(props))
            })
            .collect::<Map<String, Value>>();
        let required_params = self
            .params
            .iter()
            .filter(|param| param.required)
            .map(|param| param.name.to_string())
            .collect::<Vec<String>>();
        Ok(ChatCompletionToolArgs::default()
            .r#type(ChatCompletionToolType::Function)
            .function(
                FunctionObjectArgs::default()
                    .name(self.name)
                    .description(self.desc)
                    .parameters(json!({
                        "type": "object",
                        "properties": param_props,
                        "required": required_params,
                    }))
                    .build()?,
            )
            .build()?)
    }
}

pub struct Param {
    pub name: &'static str,
    pub ty: &'static str,
    pub desc: &'static str,
    pub required: bool,
}

impl Param {
    pub fn new(name: &'static str, ty: &'static str, required: bool, desc: &'static str) -> Self {
        Self {
            name,
            ty,
            desc,
            required,
        }
    }

    // pub fn desc(self, desc: &'static str) -> Self {
    //     Self { desc, ..self }
    // }
}

pub enum ToolError {
    Aborted,
}

pub struct Tools {
    tools: Vec<&'static GPTFunction>,
    pub yes: AtomicBool,
    pub quiet: AtomicBool,
}

impl Tools {
    pub fn new(tools: &[&'static GPTFunction]) -> Self {
        Self {
            tools: tools.to_vec(),
            yes: AtomicBool::new(false),
            quiet: AtomicBool::new(false),
        }
    }

    pub fn get_info(&self) -> Vec<ChatCompletionTool> {
        self.tools
            .iter()
            .map(|tool| tool.get_info().unwrap())
            .collect()
    }

    pub fn run(&self, name: &str, params: Value) -> Result<String, ToolError> {
        for tool in &self.tools {
            if tool.name == name {
                return (tool.handler)(params);
            }
        }
        unreachable!()
    }
}

static RUN_COMMAND: Lazy<GPTFunction> = Lazy::new(|| {
    GPTFunction {
        name: "run_command",
        desc: "Run a one-liner bash command",
        params: vec![
            Param::new("command", "string", true, "The one-liner bash command to execute. This will be directly sent to `bash -c ...` so be careful with the quotes escaping!"),
        ],
        handler: Box::new(|params| -> Result<String, ToolError> {
            let command = params["command"].as_str().unwrap().trim();
            // Show command and get user confirmation before executing
            println!("{} {}", "➜".green().bold(), command.bold());
            // Special handling for built-in commands
            if builtins::is_built_in_command(command) {
                let json = match builtins::execute_built_in_command(command) {
                    Ok(_) => json!({
                        "status_code": 0,
                        "stdout": "",
                        "stderr": "",
                    }),
                    Err(e) => json!({
                        "status_code": 1,
                        "stdout": "",
                        "stderr": e.to_string(),
                    }),
                };
                return Ok(json.to_string());
            }
            // User confirmation before executing
            if !TOOLS.yes.load(Ordering::SeqCst) && !utils::wait_for_user_acknowledgement() {
                return Err(ToolError::Aborted);
            }
            // Execute command
            let mut child = std::process::Command::new("bash")
                .arg("-c")
                .arg(command)
                .stderr(Stdio::piped())
                .stdout(Stdio::piped())
                .spawn()
                .unwrap();
            let child_stdout = child.stdout.take().unwrap();
            let child_stderr = child.stderr.take().unwrap();
            let (status, stdout, stderr) = std::thread::scope(|s| {
                let stdout_thread = s.spawn(|| -> io::Result<String> {
                    let lines = BufReader::new(child_stdout).lines();
                    let mut result = "".to_owned();
                    for line in lines {
                        let line = line.unwrap();
                        if !TOOLS.quiet.load(Ordering::SeqCst) {
                            println!("{}", line.bright_black());
                        }
                        result.push_str(&line);
                        result.push('\n');
                    }
                    Ok(result)
                });
                let stderr_thread = s.spawn(|| -> io::Result<String> {
                    let lines = BufReader::new(child_stderr).lines();
                    let mut result = "".to_owned();
                    for line in lines {
                        let line = line.unwrap();
                        if !TOOLS.quiet.load(Ordering::SeqCst) {
                            eprintln!("{}", line.bright_black());
                        }
                        result.push_str(&line);
                        result.push('\n');
                    }
                    Ok(result)
                });
                let status = child.wait().unwrap();
                let stdout = stdout_thread.join().unwrap().unwrap();
                let stderr = stderr_thread.join().unwrap().unwrap();
                (status, stdout, stderr)
            });
            let json = json!({
                "status_code": status.code().unwrap(),
                "stdout": stdout,
                "stderr": stderr,
            });
            Ok(json.to_string())
        }),
    }
});

pub static TOOLS: Lazy<Tools> = Lazy::new(|| {
    Tools::new(&[
        &RUN_COMMAND,
        // Add more tools here
    ])
});
