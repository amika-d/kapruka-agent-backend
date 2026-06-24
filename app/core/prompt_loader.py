from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from functools import lru_cache

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

@lru_cache(maxsize=None)
def _get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(PROMPTS_DIR)),
        trim_blocks=True,
        lstrip_blocks=True
    )

def render_prompt(template_name: str, **kwargs) -> str:
    env = _get_env()
    template = env.get_template(f"{template_name}.j2")
    return template.render(**kwargs)