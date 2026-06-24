from pydantic_settings import BaseSettings
import yaml
from pathlib import Path

def load_yaml_config() -> dict:
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

yaml_config = load_yaml_config()

class Settings(BaseSettings):
    openrouter_api_key: str
    kapruka_mcp_url: str = "https://mcp.kapruka.com/mcp"
    frontend_url: str = "https://kapruka.bitzandbeyond.com"
    app_env: str = "development"
    
    @property
    def model_shopper(self) -> str:
        return yaml_config["models"]["shopper"]
    
    @property  
    def model_router(self) -> str:
        return yaml_config["models"]["router"]
    
    @property
    def model_reflection(self) -> str:
        return yaml_config["models"]["reflection"]
    
    @property
    def model_concierge(self) -> str:
        return yaml_config["models"]["concierge"]
    
    @property
    def model_vision(self) -> str:
        return yaml_config["models"]["vision"]

    class Config:
        env_file = ".env"
        extra = "ignore"
        
        

settings = Settings()