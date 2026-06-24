import json
from pathlib import Path

_category_tree: dict = {}
_top_level: list[str] = []

DATA_FILE = Path(__file__).parent.parent / "data" / "kapruka_categories.json"

def load_categories_from_file():
    global _category_tree, _top_level
    with open(DATA_FILE) as f:
        _category_tree = json.load(f)
    _top_level = list(_category_tree.keys())

def get_top_level_categories() -> list[str]:
    return _top_level

def get_subcategories(parent: str) -> list[str]:
    return _category_tree.get(parent, [])

def fuzzy_match_category(hint: str) -> str | None:
    if not hint:
        return None
    hint_lower = hint.lower().strip()
    for cat in _top_level:
        if hint_lower in cat.lower() or cat.lower() in hint_lower:
            return cat
    return None


# src/core/category_cache.py
# Parse the markdown tree into structured JSON

def parse_category_tree(markdown: str) -> dict:
    """
    Returns:
    {
      "Automobile": ["Audio And Video Accessories", "Auto Care", ...],
      "cakes": ["Kapruka Cakes", "Java", "Divine", ...],
      "flowers": ["Flower Bouquets", "Birthday Flowers", ...]
    }
    """
    tree = {}
    current_parent = None
    
    for line in markdown.split("\n"):
        line = line.strip()
        if not line.startswith("-"):
            continue
        if line.startswith("- [") and not line.startswith("  "):
            # Top level
            name = line.split("](")[0].replace("- [", "").strip()
            current_parent = name
            tree[name] = []
        elif line.startswith("- [") and current_parent:
            # Subcategory
            name = line.split("](")[0].replace("- [", "").strip()
            tree[current_parent].append(name)
    
    return tree