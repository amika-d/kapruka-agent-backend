import os
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
    fal_key: str | None = None
    fal_api_key: str | None = None

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

    @property
    def tryon_app_id(self) -> str:
        # was tryon_url — fal_client takes an app id ("fal-ai/...")
        # rather than a REST URL, so this is no longer a full endpoint.
        return yaml_config["tryon"]["fal_app_id"]

    @property
    def tryon_timeout(self) -> int:
        return yaml_config["tryon"]["timeout_seconds"]

    @property
    def effective_fal_key(self) -> str | None:
        return self.fal_key or self.fal_api_key

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# fal_client reads the key from the FAL_KEY environment variable itself —
# it has no per-call "pass the key as an argument" option — so whatever
# key we resolved from either env var name needs to actually land in
# os.environ under the name fal_client expects. Doing this once here at
# import time means every fal_client call downstream just works without
# threading the key through every request.
if settings.effective_fal_key:
    os.environ.setdefault("FAL_KEY", settings.effective_fal_key)