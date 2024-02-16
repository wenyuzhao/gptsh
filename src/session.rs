use std::io::{self, Write};
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

use crate::config::Config;

pub struct ShellSession {
    client: Client<OpenAIConfig>,
    config: Config,
    history: Vec<ChatCompletionRequestMessage>,
}

impl ShellSession {
    pub fn new() -> anyhow::Result<Self> {
        let config = Config::load()?;
        Ok(Self {
            client: Client::with_config(
                OpenAIConfig::default().with_api_key(&config.openai_api_key),
            ),
            config,
            history: vec![
                ChatCompletionRequestSystemMessageArgs::default()
                .content(r#"
                    You should act as a AI terminal shell.
                    The user will send you prompts or descriptions of the tasks, instead of typing the bash commands directly.
                    You should take the prompts and descriptions, and then generate the bash commands to execute the tasks.
                "#)
                .build()?
                .into(),
            ],
        })
    }

    fn get_prompt() -> anyhow::Result<String> {
        print!("> ");
        io::stdout().flush()?;
        let mut prompt = String::new();
        io::stdin().read_line(&mut prompt)?;
        Ok(prompt)
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

    fn execute_bash_command(&self, command: &str) -> anyhow::Result<String> {
        println!("RUN: {}", command);

        std::thread::sleep(std::time::Duration::from_secs(3));

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

        // println!("RESULT: {}", json.to_string());

        Ok(json.to_string())
    }

    fn execute_tool_call(
        &self,
        tool_call: &ChatCompletionMessageToolCall,
    ) -> anyhow::Result<String> {
        assert_eq!(tool_call.function.name, "run_command");
        let args = serde_json::Value::from_str(&tool_call.function.arguments).unwrap();
        let command = args
            .as_object()
            .and_then(|args| args.get("command"))
            .and_then(|command| command.as_str())
            .map(|command| command.to_owned())
            .unwrap();
        let result = self.execute_bash_command(&command)?;
        Ok(result)
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
        while response.tool_calls.is_some() {
            let tool_calls = response.tool_calls.as_ref().unwrap();
            for tool_call in tool_calls {
                let tool_result = self.execute_tool_call(tool_call).unwrap();
                self.history.push(ChatCompletionRequestMessage::Tool(
                    ChatCompletionRequestToolMessage {
                        content: tool_result,
                        role: Role::Tool,
                        tool_call_id: tool_call.id.clone(),
                    },
                ));
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
            let prompt = Self::get_prompt()?;
            self.run_prompt(&prompt).await?;
        }
    }

    pub async fn run_single_prompt(&mut self, prompt: &str) -> anyhow::Result<()> {
        self.run_prompt(&prompt).await?;
        Ok(())
    }
}
