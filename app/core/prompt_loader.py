import re
from pathlib import Path
from functools import lru_cache
from jinja2 import Environment, FileSystemLoader

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------
# Templates sometimes get edited with "======" or "### Section" style dividers
# for human readability (see router.j2 / shopper.j2 / concierge.j2). Those are
# great for us when reading the .j2 files, but if they leak into the actual
# string sent to the model API, the model can start echoing them back as
# literal separators/icons in user-facing replies. Strip them after
# rendering, not in the templates themselves, so authors can keep using
# dividers freely without worrying about output hygiene.

# Matches lines that are made up entirely of markdown/divider "noise"
# characters (#, =, -, *, ~, _) with optional surrounding whitespace.
_DIVIDER_LINE_RE = re.compile(r"^[ \t]*[#=\-*~_]{3,}[ \t]*$", re.MULTILINE)

# Matches leading markdown heading markers ("## ", "### ", etc.) at the
# start of a line, keeping the heading text itself.
_HEADING_MARKER_RE = re.compile(r"^[ \t]*#{1,6}[ \t]*", re.MULTILINE)

# Collapse 3+ blank lines left behind after stripping dividers.
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _sanitize_rendered_prompt(text: str) -> str:
    """Remove structural markdown noise (divider lines, stray '#' headers)
    that templates use for human readability but that should never be sent
    to the model as literal content."""
    text = _DIVIDER_LINE_RE.sub("", text)
    text = _HEADING_MARKER_RE.sub("", text)
    text = _EXCESS_BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Jinja environment
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(PROMPTS_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_prompt(template_name: str, **kwargs) -> str:
    env = _get_env()
    template = env.get_template(f"{template_name}.j2")
    raw = template.render(**kwargs)
    return _sanitize_rendered_prompt(raw)