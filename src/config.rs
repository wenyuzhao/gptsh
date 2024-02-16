use serde::Deserialize;

use once_cell::sync::Lazy;

pub static CONFIG: Lazy<Config> = Lazy::new(|| Config::load().unwrap());

#[derive(Deserialize)]
pub struct Config {
    #[serde(rename = "openai-api-key")]
    pub openai_api_key: String,
}

impl Config {
    pub fn load() -> anyhow::Result<Self> {
        let home_dir =
            home::home_dir().ok_or_else(|| anyhow::anyhow!("Could not find home directory"))?;
        let config_str = std::fs::read_to_string(home_dir.join(".gptsh.toml"))?;
        let config: Config = toml::from_str(&config_str)?;
        Ok(config)
    }
}
