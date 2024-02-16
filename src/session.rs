use std::process::Command;
use std::str::FromStr;

use async_openai::config::OpenAIConfig;
use async_openai::types::{
    ChatCompletionMessageToolCall, ChatCompletionRequestAssistantMessage,
    ChatCompletionRequestMessage, ChatCompletionRequestSystemMessageArgs,
    ChatCompletionRequestToolMessage, ChatCompletionRequestUserMessageArgs,
    ChatCompletionResponseMessage, ChatCompletionToolArgs, ChatCompletionToolType,
    CreateChatCompletionRequestArgs, FunctionObjectArgs, Role,
};
use async_openai::Client;
use serde_json::json;

use crate::config::{Config, PlatformInfo};
use crate::utils;

pub struct ShellSession {
    client: Client<OpenAIConfig>,
    config: Config,
    history: Vec<ChatCompletionRequestMessage>,
}

impl ShellSession {
    pub fn new() -> anyhow::Result<Self> {
        let config = Config::load()?;
        let platform_info = PlatformInfo::load()?;
        Ok(Self {
            client: Client::with_config(
                OpenAIConfig::default().with_api_key(&config.openai_api_key),
            ),
            config,
            history: vec![
                ChatCompletionRequestSystemMessageArgs::default()
                .content(format!("
                    You should act as a AI terminal shell.
                    The user will send you prompts or descriptions of the tasks, instead of typing the bash commands directly.
                    You should take the prompts and descriptions, and then generate the bash commands to execute the tasks.
                    Don't do anything else that the user doesn't ask for, or not relevant to the tasks.

                    {}
                ", platform_info.dump_as_prompt()))
                .build()?
                .into(),
            ],
        })
    }

    #[allow(deprecated)]
    fn response_to_request_message(
        &self,
        response: ChatCompletionResponseMessage,
    ) -> ChatCompletionRequestMessage {
        match response.role {
            Role::Assistant => {
                ChatCompletionRequestMessage::Assistant(ChatCompletionRequestAssistantMessage {
                    content: response.content,
                    role: Role::Assistant,
                    name: None,
                    tool_calls: response.tool_calls,
                    function_call: response.function_call,
                })
            }
            _ => unreachable!(),
        }
    }

    async fn send_chat_request(
        &mut self,
        messages: Vec<ChatCompletionRequestMessage>,
    ) -> anyhow::Result<ChatCompletionResponseMessage> {
        let request = CreateChatCompletionRequestArgs::default()
            .model("gpt-3.5-turbo")
            .messages(messages)
            .tools(vec![ChatCompletionToolArgs::default()
                .r#type(ChatCompletionToolType::Function)
                .function(
                    FunctionObjectArgs::default()
                        .name("run_command")
                        .description("Run a bash command")
                        .parameters(json!({
                            "type": "object",
                            "properties": {
                                "command": {
                                    "type": "string",
                                    "description": "The command to execute",
                                },
                            },
                            "required": ["command"],
                        }))
                        .build()?,
                )
                .build()?])
            .build()?;
        let response = self.client.chat().create(request).await?;
        let response_message = response.choices[0].message.clone();
        Ok(response_message)
    }

    fn execute_bash_command(&self, command: &str) -> BashCmdResult {
        // Show command and get user confirmation before executing
        println!("⌛️ {}", command);
        if !utils::wait_for_user_acknowledgement() {
            return BashCmdResult::Aborted;
        }
        // Execute command
        let output = Command::new("bash")
            .args(["-c", &command])
            .output()
            .expect("Failed to execute command");
        let status = output.status.code().unwrap();
        let stdout = String::from_utf8(output.stdout).unwrap();
        let stderr = String::from_utf8(output.stderr).unwrap();
        let json = json!({
            "status_code": status,
            "stdout": stdout,
            "stderr": stderr,
        });
        BashCmdResult::Finished(json.to_string())
    }

    fn execute_tool_call(&self, tool_call: &ChatCompletionMessageToolCall) -> (String, bool) {
        assert_eq!(tool_call.function.name, "run_command");
        let args = serde_json::Value::from_str(&tool_call.function.arguments).unwrap();
        let command = args
            .as_object()
            .and_then(|args| args.get("command"))
            .and_then(|command| command.as_str())
            .map(|command| command.to_owned())
            .unwrap();
        let (result, aborted) = match self.execute_bash_command(&command) {
            BashCmdResult::Finished(result) => (result, false),
            BashCmdResult::Aborted => {
                let json = json!({
                    "error": "User cancelled the command. Task should be considered as failed and finished early.",
                });
                (json.to_string(), true)
            }
        };
        (result, aborted)
    }

    async fn send_chat_request_and_fullfill_tool_calls(
        &mut self,
        messages: Vec<ChatCompletionRequestMessage>,
    ) -> anyhow::Result<ChatCompletionResponseMessage> {
        assert!(!messages.is_empty());
        let mut response = self.send_chat_request(messages).await?;
        self.history
            .push(self.response_to_request_message(response.clone()));
        if let Some(content) = response.content.as_ref() {
            println!("{}", content);
        }
        'outer: while response.tool_calls.is_some() {
            let tool_calls = response.tool_calls.as_ref().unwrap();
            for tool_call in tool_calls {
                let (tool_result, aborted) = self.execute_tool_call(tool_call);
                self.history.push(ChatCompletionRequestMessage::Tool(
                    ChatCompletionRequestToolMessage {
                        content: tool_result,
                        role: Role::Tool,
                        tool_call_id: tool_call.id.clone(),
                    },
                ));
                if aborted {
                    break 'outer;
                }
            }
            response = self.send_chat_request(self.history.clone()).await?;
            self.history
                .push(self.response_to_request_message(response.clone()));
            if let Some(content) = response.content.as_ref() {
                println!("{}", content);
            }
        }
        Ok(response)
    }

    async fn run_prompt(&mut self, prompt: &str) -> anyhow::Result<()> {
        let mut history = self.history.clone();
        history.push(
            ChatCompletionRequestUserMessageArgs::default()
                .content(prompt)
                .build()?
                .into(),
        );
        let _response = self
            .send_chat_request_and_fullfill_tool_calls(history)
            .await?;
        Ok(())
    }

    pub async fn run_repl(&mut self) -> anyhow::Result<()> {
        loop {
            let prompt = utils::read_user_prompt()?;
            if prompt.trim().is_empty() {
                continue;
            }
            if prompt.trim() == "exit" {
                return Ok(());
            }
            self.run_prompt(&prompt).await?;
        }
    }

    pub async fn run_single_prompt(&mut self, prompt: &str) -> anyhow::Result<()> {
        self.run_prompt(&prompt).await?;
        Ok(())
    }
}

enum BashCmdResult {
    Finished(String),
    Aborted,
}
