use std::{
    collections::HashMap,
    fmt::{self, Display},
};

use serde::{Deserialize, Serialize};

const MINIMAL_CONFIG: &str = r#"
# GPT-Shell Configuration File

# OpenAI API Key
openai-api-key = "Your OpenAI API Key Here"
"#;

#[derive(Deserialize)]
pub struct Config {
    #[serde(rename = "openai-api-key")]
    pub openai_api_key: Option<String>,
}

impl Config {
    pub fn load() -> anyhow::Result<Self> {
        let home_dir =
            home::home_dir().ok_or_else(|| anyhow::anyhow!("Could not find home directory"))?;
        let config_path = home_dir.join(".config").join("gptsh").join("config.toml");
        if !config_path.exists() {
            // Create an empty config file
            std::fs::create_dir_all(config_path.parent().unwrap())?;
            std::fs::write(&config_path, MINIMAL_CONFIG.trim())?;
        }
        let config_str = std::fs::read_to_string(&config_path)?;
        let config: Config = toml::from_str(&config_str)?;
        // Validate the config
        if config.openai_api_key.is_none()
            || !config.openai_api_key.as_ref().unwrap().starts_with("sk-")
        {
            anyhow::bail!(
                "Please set your OpenAI API key in {}",
                config_path.display()
            );
        }
        Ok(config)
    }
}

#[derive(Deserialize, Serialize, Clone)]
pub struct PlatformInfo {
    pub os: String,
    pub arch: String,
    pub user: String,
    pub env_vars: HashMap<String, String>,
}

impl PlatformInfo {
    pub fn load() -> anyhow::Result<Self> {
        Ok(Self {
            os: whoami::distro(),
            arch: whoami::arch().to_string(),
            user: whoami::username(),
            env_vars: std::env::vars().collect(),
        })
    }

    pub(crate) fn dump_as_prompt(&self) -> String {
        let prompt = PlatformInfoPrompt { info: self.clone() };
        format!("{}", prompt)
    }
}

struct PlatformInfoPrompt {
    info: PlatformInfo,
}

impl Display for PlatformInfoPrompt {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(f, "Platform Information:")?;
        writeln!(f, "    OS: {}", self.info.os)?;
        writeln!(f, "    ARCH: {}", self.info.arch)?;
        writeln!(f, "    USER: {}", self.info.user)?;
        Ok(())
    }
}
