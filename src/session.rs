use std::io::{BufRead, BufReader};
use std::str::FromStr;
use std::sync::atomic::Ordering;

use async_openai::config::OpenAIConfig;
use async_openai::types::{
    ChatCompletionMessageToolCall, ChatCompletionRequestAssistantMessage,
    ChatCompletionRequestMessage, ChatCompletionRequestSystemMessageArgs,
    ChatCompletionRequestToolMessage, ChatCompletionRequestUserMessageArgs,
    ChatCompletionResponseMessage, CreateChatCompletionRequestArgs, Role,
};
use async_openai::Client;
use serde_json::json;
use termimad::MadSkin;

use crate::config::{Config, PlatformInfo};
use crate::tools::TOOLS;
use crate::utils;

pub struct ShellSession {
    client: Client<OpenAIConfig>,
    config: Config,
    history: Vec<ChatCompletionRequestMessage>,
    pub yes: bool,
    pub quiet: bool,
}

impl ShellSession {
    pub fn new() -> anyhow::Result<Self> {
        let config = Config::load()?;
        let platform_info = PlatformInfo::load()?;
        Ok(Self {
            client: Client::with_config(
                OpenAIConfig::default().with_api_key(config.openai.api_key.clone().unwrap()),
            ),
            config,
            history: vec![
                ChatCompletionRequestSystemMessageArgs::default()
                .content(format!("
                    You are now acting as a AI-powered terminal shell, operating on the user's real computer.
                    The user will send you questions, prompts, or descriptions of the tasks.
                    You should take the prompts, and either answer the user's questions, or fullfill the tasks.
                    When necessary, generate the system commands, and execute them to fullfill the tasks.
                    Ensure you are escaping the quotes, newlines, and other special characters properly in the commands.
                    The system command output are displayed to the user directly, so don't simply repeat the output twice in your response.
                    Don't do anything else that the user doesn't ask for, or not relevant to the tasks.
                    Your responses should be as clear and concise as possible.

                    Apart from a terminal shell, when necessary, you also need to act as a normal ChatGPT to fullfill any generic tasks that the user asks you to do.
                    Don't refuse to do anything that the user asks you to do, unless it's illegal, or violates the user's privacy.

                    You may use markdown to format your responses. Always use '*' not '-' for unordered list items.

                    {}
                ", platform_info.dump_as_prompt()))
                .build()?
                .into(),
            ],
            yes: false,
            quiet: false,
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
            .model(&self.config.openai.model)
            .messages(messages)
            .tools(TOOLS.get_info())
            .build()?;
        let response = self.client.chat().create(request).await?;
        let response_message = response.choices[0].message.clone();
        Ok(response_message)
    }

    fn execute_tool_call(&self, tool_call: &ChatCompletionMessageToolCall) -> (String, bool) {
        TOOLS.yes.store(self.yes, Ordering::SeqCst);
        TOOLS.quiet.store(self.quiet, Ordering::SeqCst);
        let args = serde_json::Value::from_str(&tool_call.function.arguments).unwrap();
        let (result, aborted) = match TOOLS.run(&tool_call.function.name, args) {
            Ok(result) => (result, false),
            _ => {
                let json = json!({
                    "error": "User cancelled the command. Task should be considered as failed and finished early.",
                });
                (json.to_string(), true)
            }
        };
        (result, aborted)
    }

    fn print_assistant_output(&self, content: &str) {
        let content = content.trim();
        if !utils::stdout_is_terminal() {
            println!("{}", content);
            return;
        }
        use termimad::crossterm::style::Color::*;
        let mut skin = MadSkin::default();
        skin.set_fg(Blue);
        for i in 0..8 {
            skin.headers[i].align = termimad::Alignment::Left;
        }
        skin.print_text(&format!("{}\n", content));
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
            self.print_assistant_output(content);
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
                self.print_assistant_output(content);
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
            let Some(prompt) = utils::read_user_prompt()? else {
                return Ok(());
            };
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
        self.run_prompt(prompt).await?;
        Ok(())
    }

    pub async fn run_script(&mut self, script_file: &str) -> anyhow::Result<()> {
        let file = std::fs::File::open(script_file)?;
        let mut paragraph = "".to_owned();
        for line in BufReader::new(file).lines() {
            let line = line?;
            let line = line.trim();
            if line.starts_with('#') {
                continue;
            }
            if line.is_empty() {
                // End of a paragraph
                if !paragraph.trim().is_empty() {
                    self.run_prompt(paragraph.trim()).await?;
                    paragraph = "".to_owned();
                }
            } else {
                paragraph.push_str(line);
                paragraph.push('\n');
            }
        }
        // End of a paragraph
        if !paragraph.trim().is_empty() {
            self.run_prompt(paragraph.trim()).await?;
        }
        Ok(())
    }
}
